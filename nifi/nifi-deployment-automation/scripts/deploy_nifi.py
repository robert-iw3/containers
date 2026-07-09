import os
import subprocess
import logging
import shutil
import pwd
import grp
import ansible_runner
import secrets
import datetime
from pathlib import Path
from typing import List, Dict

# Configuration
CONFIG = {
    "ansible_playbook": "ansible/playbook.yml",
    "systemd_template": "ansible/templates/systemd-unit.j2",
    "ansible_vault_file": "ansible/secrets.yml",
    "ansible_vault_password_file": ".ansible_vault_pass.txt",
    "nifi_domain": "nifi.example.com",
    "s3_bucket": "bucket",
    "backup_dir": "backups",
    "log_file": "logs/deploy-nifi.log",
    "podman_systemd_user": "nifi",
    "aws_credentials_file": f"/home/nifi/.aws/credentials",
    "prometheus_config": "prometheus/prometheus.yml",
}

# Setup logging
Path(CONFIG["log_file"]).parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    handlers=[
        logging.FileHandler(CONFIG["log_file"]),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_command(command: List[str], check: bool = True, user: str = None) -> subprocess.CompletedProcess:
    """Run a shell command, optionally as a specific user."""
    if user:
        command = ["sudo", "-u", user] + command
    try:
        return subprocess.run(command, check=check, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {command}\n{e.stderr}")
        raise

def check_requirements() -> None:
    """Check if required tools are installed."""
    logger.info("Checking for required tools")
    tools = ["ansible", "ansible-playbook", "podman", "git", "curl", "aws"]
    for tool in tools:
        if not shutil.which(tool):
            logger.error(f"{tool} is required but not installed.")
            raise SystemExit(1)

def create_nifi_user() -> None:
    """Create NiFi user and configure environment."""
    logger.info("Creating NiFi user and configuring environment")
    try:
        pwd.getpwnam(CONFIG["podman_systemd_user"])
        logger.info(f"NiFi user {CONFIG['podman_systemd_user']} already exists")
    except KeyError:
        run_command([
            "sudo", "useradd", "-m", "-s", "/bin/bash",
            "-G", "wheel,systemd-journal", CONFIG["podman_systemd_user"]
        ])
        logger.info(f"Created NiFi user: {CONFIG['podman_systemd_user']}")

    # Configure subuid and subgid
    for file_path in ["/etc/subuid", "/etc/subgid"]:
        with open(file_path, "r") as f:
            if not any(line.startswith(f"{CONFIG['podman_systemd_user']}:") for line in f):
                run_command([
                    "sudo", "bash", "-c",
                    f"echo '{CONFIG['podman_systemd_user']}:165536:65536' >> {file_path}"
                ])

    # Enable lingering
    run_command(["sudo", "loginctl", "enable-linger", CONFIG["podman_systemd_user"]], check=False)
    if not Path(f"/var/lib/systemd/linger/{CONFIG['podman_systemd_user']}").exists():
        logger.warning(f"Failed to enable lingering for {CONFIG['podman_systemd_user']}.")

    # Configure sudoers
    sudoers_content = f"{CONFIG['podman_systemd_user']} ALL=(ALL) NOPASSWD:/usr/bin/podman,/bin/systemctl\n"
    sudoers_file = "/etc/sudoers.d/nifi"
    run_command(["sudo", "bash", "-c", f"echo '{sudoers_content}' > {sudoers_file}"])
    run_command(["sudo", "chmod", "0440", sudoers_file])
    try:
        run_command(["sudo", "visudo", "-cf", sudoers_file])
    except subprocess.CalledProcessError:
        logger.error("Invalid sudoers configuration.")
        raise SystemExit(1)

def install_ansible() -> None:
    """Install Ansible and required collections."""
    logger.info(f"Installing Ansible as {CONFIG['podman_systemd_user']}")
    run_command([
        "sudo", "-u", CONFIG["podman_systemd_user"],
        "pip3", "install", "--user", "ansible", "ansible-core"
    ])
    run_command([
        "sudo", "-u", CONFIG["podman_systemd_user"],
        "ansible-galaxy", "collection", "install", "community.crypto", "containers.podman", "--force"
    ])

def install_certbot() -> None:
    """Install Certbot."""
    logger.info("Installing certbot")
    try:
        run_command(["sudo", "dnf", "install", "-y", "certbot", "python3-certbot"])
    except subprocess.CalledProcessError:
        logger.error("Failed to install certbot.")
        raise SystemExit(1)

def setup_vault() -> None:
    """Set up Ansible Vault for secrets."""
    logger.info("Setting up Ansible Vault for secrets")
    vault_pass_file = Path(CONFIG["ansible_vault_password_file"])
    if not vault_pass_file.exists():
        vault_password = secrets.token_urlsafe(32)
        run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "bash", "-c",
                     f"echo '{vault_password}' > {vault_pass_file}"])
        run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "chmod", "600", vault_pass_file])
        logger.info(f"Generated vault password file: {vault_pass_file}")

    vault_file = Path(CONFIG["ansible_vault_file"])
    if not vault_file.exists():
        vault_content = """vault_nifi_password: securePassword123
vault_jks_password: secureKeystore123
"""
        vault_file.parent.mkdir(parents=True, exist_ok=True)
        run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "bash", "-c",
                     f"echo '{vault_content}' > {vault_file}"])
        run_command([
            "sudo", "-u", CONFIG["podman_systemd_user"],
            "ansible-vault", "encrypt", vault_file, "--vault-password-file", vault_pass_file
        ])
        logger.info(f"Created and encrypted vault file: {vault_file}")

def configure_aws() -> None:
    """Configure AWS CLI for S3 backups."""
    logger.info("Configuring AWS CLI for S3 backups")
    aws_credentials_file = Path(CONFIG["aws_credentials_file"])
    if not aws_credentials_file.exists():
        aws_credentials_file.parent.mkdir(parents=True, exist_ok=True)
        aws_content = """[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
"""
        run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "bash", "-c",
                     f"echo '{aws_content}' > {aws_credentials_file}"])
        run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "chmod", "600", aws_credentials_file])
        logger.warning(f"AWS credentials file created with placeholder values. Update {aws_credentials_file}.")

def validate_files() -> None:
    """Validate playbook and template files."""
    logger.info("Validating playbook and template files")
    for file in [CONFIG["ansible_playbook"], CONFIG["systemd_template"]]:
        if not Path(file).exists():
            logger.error(f"{file} not found.")
            raise SystemExit(1)
        run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "chmod", "644", file])

def run_playbook() -> None:
    """Run Ansible playbook."""
    logger.info(f"Running Ansible playbook as {CONFIG['podman_systemd_user']}: {CONFIG['ansible_playbook']}")
    runner = ansible_runner.run(
        private_data_dir="ansible",
        playbook=CONFIG["ansible_playbook"],
        extravars={"nifi_domain": CONFIG["nifi_domain"]},
        vault_password_file=CONFIG["ansible_vault_password_file"],
        cmdline=f"--user {CONFIG['podman_systemd_user']}"
    )
    if runner.status != "successful":
        logger.error("Failed to run Ansible playbook.")
        raise SystemExit(1)

def verify_deployment() -> None:
    """Verify NiFi and NiFi-Registry deployment."""
    logger.info("Verifying NiFi deployment")
    try:
        result = run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "podman", "ps"])
        if "nifi" not in result.stdout:
            logger.error("NiFi container is not running.")
            raise SystemExit(1)
        result = run_command(["systemctl", "is-active", "--quiet", "container-nifi.service"])
        if result.returncode != 0:
            logger.error("NiFi service is not active.")
            raise SystemExit(1)
        result = run_command([
            "sudo", "-u", CONFIG["podman_systemd_user"], "curl", "-k", "-s", "-f",
            f"https://{CONFIG['nifi_domain']}:8443/nifi"
        ], check=False)
        if result.returncode != 0:
            logger.warning(f"NiFi web interface not accessible at https://{CONFIG['nifi_domain']}:8443/nifi.")
        else:
            logger.info("NiFi web interface is accessible.")

        # Verify NiFi-Registry
        result = run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "podman", "ps"])
        if "nifi-registry" not in result.stdout:
            logger.error("NiFi-Registry container is not running.")
            raise SystemExit(1)
        result = run_command(["systemctl", "is-active", "--quiet", "container-nifi-registry.service"])
        if result.returncode != 0:
            logger.error("NiFi-Registry service is not active.")
            raise SystemExit(1)
        result = run_command([
            "sudo", "-u", CONFIG["podman_systemd_user"], "curl", "-k", "-s", "-f",
            f"https://{CONFIG['nifi_domain']}:18080/nifi-registry"
        ], check=False)
        if result.returncode != 0:
            logger.warning(f"NiFi-Registry web interface not accessible at https://{CONFIG['nifi_domain']}:18080/nifi-registry.")
        else:
            logger.info("NiFi-Registry web interface is accessible.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Verification failed: {e.stderr}")
        raise SystemExit(1)

def setup_monitoring() -> None:
    """Set up Prometheus monitoring."""
    logger.info("Setting up Prometheus monitoring")
    prometheus_config = Path(CONFIG["prometheus_config"])
    prometheus_config.parent.mkdir(parents=True, exist_ok=True)
    prometheus_content = f"""global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'nifi'
    static_configs:
      - targets: ['{CONFIG['nifi_domain']}:8443']
    metrics_path: /nifi-metrics
    scheme: https
  - job_name: 'nifi-registry'
    static_configs:
      - targets: ['{CONFIG['nifi_domain']}:18080']
    metrics_path: /nifi-registry-metrics
    scheme: https
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
"""
    run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "bash", "-c",
                 f"echo '{prometheus_content}' > {prometheus_config}"])
    run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "chmod", "644", prometheus_config])
    try:
        run_command([
            "sudo", "-u", CONFIG["podman_systemd_user"], "podman", "run", "-d",
            "--name", "prometheus", "--network", "nifi", "-p", "9090:9090",
            "-v", f"{prometheus_config}:/etc/prometheus/prometheus.yml:Z",
            "prom/prometheus:latest"
        ])
    except subprocess.CalledProcessError:
        logger.warning("Failed to start Prometheus container.")

def setup_backup_verification() -> None:
    """Set up backup verification cron job."""
    logger.info("Setting up backup verification")
    Path(CONFIG["backup_dir"]).mkdir(parents=True, exist_ok=True)
    backup_verify_script = f"scripts/nifi-backup-verify.sh"
    backup_verify_content = f"""#!/bin/bash
aws s3 ls s3://{CONFIG['s3_bucket']}/nifi-backup-$(date +%Y%m%d).tar.gz || {{
    echo 'Backup for $(date +%Y%m%d) not found!' | mail -s 'NiFi Backup Failure' admin@example.com
}}
"""
    run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "bash", "-c",
                 f"echo '{backup_verify_content}' > {backup_verify_script}"])
    run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "chmod", "+x", backup_verify_script])

    cron_file = f"/home/{CONFIG['podman_systemd_user']}/nifi-backup.cron"
    cron_content = f"0 3 * * * /home/{CONFIG['podman_systemd_user']}/{backup_verify_script}\n"
    run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "bash", "-c",
                 f"echo '{cron_content}' > {cron_file}"])
    run_command(["sudo", "-u", CONFIG["podman_systemd_user"], "crontab", cron_file])
    logger.info(f"Configured backup verification cron job for {CONFIG['podman_systemd_user']}")

def main() -> None:
    """Main deployment function."""
    logger.info(f"Starting NiFi and NiFi-Registry deployment process at {datetime.datetime.now()}")
    check_requirements()
    create_nifi_user()
    install_ansible()
    install_certbot()
    setup_vault()
    configure_aws()
    validate_files()
    run_playbook()
    verify_deployment()
    setup_monitoring()
    setup_backup_verification()
    logger.info(f"Deployment completed successfully at {datetime.datetime.now()}")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        logger.error(f"Deployment failed with exit code {e.code}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise SystemExit(1)