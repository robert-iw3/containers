import subprocess
import boto3
import re
import os
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from time import sleep
import shutil
import botocore.exceptions
import logging.handlers
import requests
import yaml

# Configure logging with rotation
def setup_logging(log_file: str) -> None:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(console_handler)

class NomadDeployer:
    def __init__(self, config: Dict):
        self.project_dir = Path(config["project_dir"])
        self.tf_vars_file = Path(config["tf_vars_file"])
        self.aws_region = config["aws_region"]
        self.secondary_region = config.get("secondary_region", "us-west-2")
        self.cluster_name = config["cluster_name"]
        self.ssl_cert_arn = config["ssl_cert_arn"]
        self.ssh_key_path = Path(config["ssh_key_path"]).expanduser()
        self.log_file = config["log_file"]
        self.retry_attempts = config.get("retry_attempts", 5)
        self.retry_delay = config.get("retry_delay", 5)
        self.ami_id = None
        self.nomad_token = None
        self.consul_token = None
        self.vault_token = None
        self.grafana_admin_password = None
        self.ec2_client = boto3.client("ec2", region_name=self.aws_region)
        self.secrets_client = boto3.client("secretsmanager", region_name=self.aws_region)
        self.kms_client = boto3.client("kms", region_name=self.aws_region)
        self.budgets_client = boto3.client("budgets", region_name=self.aws_region)
        self.tf_state_bucket = "nomad-terraform-state"
        self.tf_state_key = "nomad-cluster/terraform.tfstate"
        setup_logging(self.log_file)

    def check_prerequisites(self) -> None:
        """Validate that required tools and configurations are present."""
        logger = logging.getLogger(__name__)
        logger.info("Checking prerequisites...")
        for cmd in ["terraform", "packer", "aws"]:
            if not shutil.which(cmd):
                raise RuntimeError(f"{cmd} is not installed or not in PATH")
        try:
            self.run_command(["aws", "sts", "get-caller-identity"], capture_output=False)
        except subprocess.CalledProcessError:
            raise RuntimeError("AWS CLI is not configured with valid credentials")
        if not self.ssh_key_path.exists():
            raise RuntimeError(f"SSH key not found at {self.ssh_key_path}")
        try:
            self.ec2_client.describe_regions(regions=[self.aws_region, self.secondary_region])
        except botocore.exceptions.ClientError:
            raise RuntimeError(f"Invalid AWS region: {self.aws_region} or {self.secondary_region}")

    def run_command(self, command: List[str], cwd: Optional[Path] = None, capture_output: bool = True, retries: int = None) -> subprocess.CompletedProcess:
        """Run a shell command with retries."""
        logger = logging.getLogger(__name__)
        retries = retries or self.retry_attempts
        for attempt in range(1, retries + 1):
            try:
                result = subprocess.run(
                    command, cwd=cwd or self.project_dir, capture_output=capture_output, text=True, check=True
                )
                logger.info(f"Command {' '.join(command)} succeeded")
                return result
            except subprocess.CalledProcessError as e:
                logger.warning(f"Command {' '.join(command)} failed (attempt {attempt}/{retries}): {e.stderr}")
                if attempt == retries:
                    raise
                sleep(self.retry_delay)

    def build_packer_ami(self) -> str:
        """Build the Packer AMI and extract the AMI ID."""
        logger = logging.getLogger(__name__)
        logger.info("Building Packer AMI...")
        packer_dir = self.project_dir / "packer"
        result = self.run_command(["packer", "build", "nomad-podman-ami.pkr.hcl"], cwd=packer_dir)
        ami_match = re.search(r"AMIs were created:\n.*(ami-[0-9a-f]+)", result.stdout)
        if not ami_match:
            raise RuntimeError("Failed to extract AMI ID from Packer output")
        self.ami_id = ami_match.group(1)
        logger.info(f"Built AMI: {self.ami_id}")
        return self.ami_id

    def update_tf_vars(self) -> None:
        """Update variables.tfvars with AMI ID, cluster name, and SSL certificate ARN."""
        logger = logging.getLogger(__name__)
        logger.info(f"Updating {self.tf_vars_file}...")
        tf_vars_content = f"""
aws_region          = "{self.aws_region}"
secondary_region    = "{self.secondary_region}"
cluster_name        = "{self.cluster_name}"
nomad_ami_id        = "{self.ami_id}"
consul_ami_id       = "{self.ami_id}"
vault_ami_id        = "{self.ami_id}"
ssl_certificate_arn = "{self.ssl_cert_arn}"
num_nomad_servers   = 3
num_nomad_clients   = 3
num_consul_servers  = 3
num_vault_servers   = 3
server_instance_type = "t3.medium"
client_instance_type = "t3.large"
grafana_admin_password = "initial-password"
"""
        if self.tf_vars_file.exists():
            logger.info(f"Overwriting existing {self.tf_vars_file}")
        self.tf_vars_file.write_text(tf_vars_content.strip())
        logger.info(f"Updated {self.tf_vars_file}")

    def create_budget(self) -> None:
        """Create AWS Budget for cost monitoring."""
        logger = logging.getLogger(__name__)
        logger.info("Creating AWS Budget...")
        budget_data = {
            "BudgetName": f"{self.cluster_name}-budget",
            "BudgetLimit": {"Amount": "1000", "Unit": "USD"},
            "CostTypes": {"IncludeTax": True, "IncludeSubscription": True},
            "TimeUnit": "MONTHLY",
            "TimePeriod": {
                "Start": "2025-01-01_00:00",
                "End": "2030-01-01_00:00"
            },
            "Notifications": [{
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 80,
                "ThresholdType": "PERCENTAGE",
                "SubscriberSnsTopicArns": []
            }]
        }
        budget_file = self.project_dir / "budget.json"
        budget_file.write_text(json.dumps(budget_data, indent=2))
        logger.info("Created budget.json")

    def terraform_init(self) -> None:
        """Initialize Terraform."""
        logger = logging.getLogger(__name__)
        logger.info("Initializing Terraform...")
        self.run_command(["terraform", "init"])

    def terraform_apply(self) -> None:
        """Apply Terraform configuration."""
        logger = logging.getLogger(__name__)
        logger.info("Applying Terraform configuration...")
        self.run_command(["terraform", "apply", "-var-file", str(self.tf_vars_file), "-auto-approve"])

    def get_terraform_outputs(self) -> Dict:
        """Retrieve Terraform outputs."""
        logger = logging.getLogger(__name__)
        logger.info("Retrieving Terraform outputs...")
        result = self.run_command(["terraform", "output", "-json"])
        return json.loads(result.stdout)

    def retrieve_secrets(self, secrets_arn: str) -> None:
        """Retrieve secrets from AWS Secrets Manager."""
        logger = logging.getLogger(__name__)
        logger.info(f"Retrieving secrets from {secrets_arn}...")
        try:
            secret = self.secrets_client.get_secret_value(SecretId=secrets_arn)
            secret_dict = json.loads(secret["SecretString"])
            self.nomad_token = secret_dict["nomad_acl_token"]
            self.vault_token = secret_dict["vault_token"]
            self.grafana_admin_password = secret_dict["grafana_admin_password"]
            logger.info("Successfully retrieved secrets")
        except Exception as e:
            logger.error(f"Failed to retrieve secrets: {str(e)}")
            raise

    def configure_consul(self, consul_ip: str) -> str:
        """Retrieve Consul ACL token from the first Consul server."""
        logger = logging.getLogger(__name__)
        logger.info(f"Configuring Consul on {consul_ip}...")
        ssh_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=accept-new", "-i", str(self.ssh_key_path),
            f"ubuntu@{consul_ip}",
            "sudo cat /etc/consul.d/acl-bootstrap.txt | grep 'SecretID' | awk '{print $NF}'"
        ]
        result = self.run_command(ssh_cmd)
        self.consul_token = result.stdout.strip()
        if not self.consul_token:
            raise RuntimeError("Failed to retrieve Consul ACL token")
        logger.info("Retrieved Consul ACL token")
        return self.consul_token

    def configure_vault(self, vault_ip: str) -> None:
        """Retrieve Vault root token and ensure Vault is unsealed."""
        logger = logging.getLogger(__name__)
        logger.info(f"Configuring Vault on {vault_ip}...")
        ssh_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=accept-new", "-i", str(self.ssh_key_path),
            f"ubuntu@{vault_ip}",
            "sudo cat /etc/vault.d/vault-init.txt | grep 'Initial Root Token' | awk '{print $NF}'"
        ]
        result = self.run_command(ssh_cmd)
        self.vault_token = result.stdout.strip()
        if not self.vault_token:
            raise RuntimeError("Failed to retrieve Vault root token")
        logger.info("Retrieved Vault root token")

    def configure_nomad_federation(self, nomad_ip_primary: str, nomad_ip_secondary: str, consul_ip_primary: str, vault_ip_primary: str) -> None:
        """Configure Nomad multi-region federation."""
        logger = logging.getLogger(__name__)
        logger.info(f"Configuring Nomad federation between {nomad_ip_primary} (primary) and {nomad_ip_secondary} (secondary)...")
        nomad_config = f"""
data_dir = "/opt/nomad/data"
log_level = "INFO"
bind_addr = "0.0.0.0"
region = "{{region}}"
datacenter = "dc1"
server {{
  enabled = true
  bootstrap_expect = 3
  encrypt = "{self.nomad_token}"
  acl {{
    enabled = true
    token_ttl = "30m"
    policy_ttl = "3h"
    token_min_ttl = "10m"
  }}
  tls {{
    http = true
    rpc = true
    ca_file = "/etc/nomad.d/ca.pem"
    cert_file = "/etc/nomad.d/nomad-cert.pem"
    key_file = "/etc/nomad.d/nomad-key.pem"
  }}
  server_join {{
    retry_join = ["{nomad_ip_primary}:4647", "{nomad_ip_secondary}:4647"]
  }}
}}
client {{
  enabled = false
  servers = ["{nomad_ip_primary}:4647", "{nomad_ip_secondary}:4647"]
  plugin "nomad-driver-podman" {{
    config {{
      enabled = true
      socket_path = "/run/user/1000/podman/podman.sock"
      volumes_enabled = true
    }}
  }}
}}
consul {{
  address = "{consul_ip_primary}:8500"
  token = "{self.consul_token}"
  auto_advertise = true
}}
vault {{
  enabled = true
  address = "https://{vault_ip_primary}:8200"
  create_from_role = "nomad-cluster"
}}
telemetry {{
  collection_interval = "1s"
  disable_hostname = true
  prometheus_metrics = true
  publish_allocation_metrics = true
  publish_node_metrics = true
}}
service_discovery {{
  enabled = true
}}
"""
        for region, nomad_ip in [("primary", nomad_ip_primary), ("secondary", nomad_ip_secondary)]:
            config_file = self.project_dir / f"nomad-{region}.hcl"
            config_file.write_text(nomad_config.replace("{{region}}", region).strip())
            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=accept-new", "-i", str(self.ssh_key_path),
                str(config_file), f"ubuntu@{nomad_ip}:/tmp/nomad.hcl"
            ]
            self.run_command(scp_cmd)
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=accept-new", "-i", str(self.ssh_key_path),
                f"ubuntu@{nomad_ip}",
                "sudo mv /tmp/nomad.hcl /etc/nomad.d/nomad.hcl && sudo chown nomad:nomad /etc/nomad.d/nomad.hcl && sudo chmod 0600 /etc/nomad.d/nomad.hcl && sudo systemctl restart nomad"
            ]
            self.run_command(ssh_cmd)
            config_file.unlink()
        logger.info("Configured Nomad federation")

    def import_grafana_dashboards(self, grafana_lb_address: str) -> None:
        """Import Grafana dashboards for Nomad, Consul, Vault, and Fluent Bit."""
        logger = logging.getLogger(__name__)
        logger.info("Importing Grafana dashboards...")
        dashboard_files = ["nomad-dashboard.json", "consul-dashboard.json", "vault-dashboard.json", "fluent-bit-dashboard.json"]
        grafana_url = f"https://{grafana_lb_address}/api/dashboards/db"
        headers = {"Content-Type": "application/json"}

        for dashboard_file in dashboard_files:
            dashboard_path = self.project_dir / dashboard_file
            if not dashboard_path.exists():
                logger.warning(f"Dashboard file {dashboard_file} not found, skipping")
                continue
            with open(dashboard_path, "r") as f:
                dashboard_data = json.load(f)
            payload = {"dashboard": dashboard_data, "overwrite": True}
            for attempt in range(self.retry_attempts):
                try:
                    response = requests.post(grafana_url, headers=headers, json=payload, auth=("admin", self.grafana_admin_password), verify=False)
                    response.raise_for_status()
                    logger.info(f"Imported {dashboard_file} to Grafana")
                    break
                except requests.RequestException as e:
                    logger.warning(f"Failed to import {dashboard_file} (attempt {attempt + 1}/{self.retry_attempts}): {str(e)}")
                    if attempt == self.retry_attempts - 1:
                        raise
                    sleep(self.retry_delay)

    def configure_grafana_alerts(self, grafana_lb_address: str) -> None:
        """Configure Grafana alerting rules."""
        logger = logging.getLogger(__name__)
        logger.info("Configuring Grafana alerting rules...")
        alert_file = self.project_dir / "grafana-alerts.yml"
        grafana_url = f"https://{grafana_lb_address}/api/prometheus/grafana/api/v1/rules"
        headers = {
            "Content-Type": "application/yaml",
            "Accept": "application/yaml"
        }

        if not alert_file.exists():
            logger.warning("Alert file grafana-alerts.yml not found, skipping")
            return

        with open(alert_file, "r") as f:
            alert_data = f.read()

        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(grafana_url, headers=headers, data=alert_data, auth=("admin", self.grafana_admin_password), verify=False)
                response.raise_for_status()
                logger.info("Configured Grafana alerting rules")
                break
            except requests.RequestException as e:
                logger.warning(f"Failed to configure alerts (attempt {attempt + 1}/{self.retry_attempts}): {str(e)}")
                if attempt == self.retry_attempts - 1:
                    raise
                sleep(self.retry_delay)

    def verify_deployment(self, nomad_global_address: str, consul_ip: str, vault_ip: str, grafana_lb_address: str) -> None:
        """Verify the Nomad, Consul, Vault, and monitoring deployment."""
        logger = logging.getLogger(__name__)
        logger.info("Verifying deployment...")
        os.environ["NOMAD_ADDR"] = f"https://{nomad_global_address}:443"
        os.environ["NOMAD_TOKEN"] = self.nomad_token
        self.run_command(["nomad", "node", "status"])
        self.run_command(["nomad", "server", "members"])
        if consul_ip:
            self.run_command(["consul", "members"])
        if vault_ip:
            self.run_command(["curl", "-k", f"https://{vault_ip}:8200/v1/sys/health"])
        self.run_command(["nomad", "job", "run", "fluent-bit.nomad"])
        self.run_command(["curl", "-k", f"https://{grafana_lb_address}/api/health"])
        self.import_grafana_dashboards(grafana_lb_address)
        self.configure_grafana_alerts(grafana_lb_address)
        logger.info("Deployment verified successfully")

    def cleanup(self) -> None:
        """Clean up Terraform resources, Packer AMI, and KMS key if deployment fails."""
        logger = logging.getLogger(__name__)
        logger.info("Cleaning up resources...")
        try:
            self.run_command(["terraform", "destroy", "-var-file", str(self.tf_vars_file), "-auto-approve"], capture_output=False)
        except subprocess.CalledProcessError:
            logger.warning("Terraform destroy failed, some resources may remain")
        if self.ami_id:
            try:
                images = self.ec2_client.describe_images(ImageIds=[self.ami_id])["Images"]
                if images:
                    snapshot_id = images[0]["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"]
                    self.ec2_client.deregister_image(ImageId=self.ami_id)
                    self.ec2_client.delete_snapshot(SnapshotId=snapshot_id)
                    logger.info(f"Deregistered AMI {self.ami_id} and deleted snapshot {snapshot_id}")
            except botocore.exceptions.ClientError as e:
                logger.warning(f"Failed to clean up AMI {self.ami_id}: {str(e)}")
        try:
            secrets_arn = self.get_terraform_outputs().get("secrets_arn", {}).get("value")
            if secrets_arn:
                self.secrets_client.delete_secret(SecretId=secrets_arn, ForceDeleteWithoutRecovery=True)
                logger.info(f"Deleted secret {secrets_arn}")
        except Exception as e:
            logger.warning(f"Failed to delete secret: {str(e)}")
        try:
            kms_key_id = self.kms_client.list_keys()["Keys"][0]["KeyId"]
            self.kms_client.schedule_key_deletion(KeyId=kms_key_id, PendingWindowInDays=7)
            logger.info(f"Scheduled deletion of KMS key {kms_key_id}")
        except Exception as e:
            logger.warning(f"Failed to schedule KMS key deletion: {str(e)}")

    def deploy(self) -> None:
        """Execute the full deployment process."""
        logger = logging.getLogger(__name__)
        try:
            self.check_prerequisites()
            self.build_packer_ami()
            self.update_tf_vars()
            self.create_budget()
            self.terraform_init()
            self.terraform_apply()
            outputs = self.get_terraform_outputs()
            self.retrieve_secrets(outputs["secrets_arn"]["value"])
            nomad_global_address = outputs["nomad_global_address"]["value"]
            grafana_lb_address = outputs["grafana_lb_address_primary"]["value"]
            nomad_server_ips_primary = outputs["nomad_server_ips_primary"]["value"]
            nomad_server_ips_secondary = outputs["nomad_server_ips_secondary"]["value"]
            consul_ips_primary = outputs["consul_instance_ips_primary"]["value"] if outputs.get("consul_instance_ips_primary") else []
            vault_ips_primary = outputs["vault_instance_ips_primary"]["value"] if outputs.get("vault_instance_ips_primary") else []
            if consul_ips_primary:
                self.consul_token = self.configure_consul(consul_ips_primary[0])
            if vault_ips_primary:
                self.vault_token = self.configure_vault(vault_ips_primary[0])
            if nomad_server_ips_primary and nomad_server_ips_secondary:
                self.configure_nomad_federation(
                    nomad_ip_primary=nomad_server_ips_primary[0],
                    nomad_ip_secondary=nomad_server_ips_secondary[0],
                    consul_ip_primary=consul_ips_primary[0] if consul_ips_primary else "",
                    vault_ip_primary=vault_ips_primary[0] if vault_ips_primary else ""
                )
            self.verify_deployment(
                nomad_global_address=nomad_global_address,
                consul_ip=consul_ips_primary[0] if consul_ips_primary else "",
                vault_ip=vault_ips_primary[0] if vault_ips_primary else "",
                grafana_lb_address=grafana_lb_address
            )
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            self.cleanup()
            raise

def main():
    parser = argparse.ArgumentParser(description="Automate Nomad cluster deployment on AWS")
    parser.add_argument("--config", required=True, help="Path to configuration file")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    deployer = NomadDeployer(config)
    deployer.deploy()

if __name__ == "__main__":
    main()