#!/usr/bin/env python3
import os
import subprocess
import yaml
import logging
import argparse
import time
from pathlib import Path
from typing import Dict
import hashlib
import base64
from tenacity import retry, stop_after_attempt, wait_fixed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class KeycloakDeployer:
    def __init__(self, config: Dict, namespace: str = "keycloak"):
        self.config = config
        self.namespace = namespace
        self.kubectl = "kubectl"
        self.podman_compose = "podman-compose"
        self.ansible_playbook = "ansible-playbook"
        self.manifest_file = "deploy.yaml"
        self.compose_file = "docker-compose-keycloak.yml"
        self.ansible_inventory = "inventory.yml"
        self.ansible_playbook_file = "keycloak_playbook.yml"

    def validate_config(self) -> bool:
        """Validate required configuration values."""
        required_keys = [
            'POSTGRESQL_USERNAME', 'POSTGRESQL_PASSWORD', 'POSTGRESQL_DATABASE',
            'POSTGRESQL_REPLICATION_USER', 'POSTGRESQL_REPLICATION_PASSWORD',
            'KEYCLOAK_USER', 'KEYCLOAK_PASSWORD', 'TRAEFIK_AUTH_PASSWORD', 'LETSENCRYPT_EMAIL'
        ]
        for key in required_keys:
            if not self.config.get(key):
                logger.error(f"Missing required configuration: {key}")
                return False
        if not self.config['LETSENCRYPT_EMAIL'].endswith('@'):
            logger.error("Invalid Let's Encrypt email")
            return False
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def check_requirements(self) -> bool:
        """Check if required tools are installed."""
        required_tools = [self.kubectl, self.podman_compose, self.ansible_playbook, "openssl"]
        for tool in required_tools:
            try:
                subprocess.run([tool, "--version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error(f"Required tool {tool} is not installed.")
                return False
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def ensure_namespace(self) -> bool:
        """Ensure Kubernetes namespace exists."""
        logger.info(f"Ensuring namespace {self.namespace} exists")
        try:
            subprocess.run([self.kubectl, "get", "ns", self.namespace], capture_output=True, check=False)
        except subprocess.CalledProcessError:
            try:
                subprocess.run([self.kubectl, "create", "ns", self.namespace], check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create namespace {self.namespace}: {e}")
                return False
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def install_traefik_crds(self) -> bool:
        """Install Traefik CRDs."""
        logger.info("Installing Traefik CRDs")
        crd_url = "https://raw.githubusercontent.com/traefik/traefik/v2.10/traefik.crds.yaml"
        try:
            subprocess.run([self.kubectl, "apply", "-f", crd_url], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Traefik CRDs: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def install_cert_manager(self) -> bool:
        """Install cert-manager."""
        logger.info("Installing cert-manager")
        cert_manager_url = "https://github.com/cert-manager/cert-manager/releases/download/v1.15.1/cert-manager.yaml"
        try:
            subprocess.run([self.kubectl, "apply", "-f", cert_manager_url], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install cert-manager: {e}")
            return False

    def generate_hashed_password(self, password: str) -> str:
        """Generate bcrypt hashed password for Traefik auth."""
        try:
            result = subprocess.run(
                ["openssl", "passwd", "-6", password],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate hashed password: {e}")
            raise

    def update_manifest(self) -> bool:
        """Update Kubernetes manifest with configuration values."""
        logger.info(f"Updating manifest file {self.manifest_file}")
        try:
            with open(self.manifest_file, 'r') as f:
                manifest = yaml.safe_load_all(f)
                manifest_list = list(manifest)

            for doc in manifest_list:
                if doc.get('kind') == 'Secret' and doc.get('metadata', {}).get('name') == 'keycloak-secrets':
                    doc['stringData'].update({
                        'postgresql-username': self.config['POSTGRESQL_USERNAME'],
                        'postgresql-password': self.config['POSTGRESQL_PASSWORD'],
                        'postgresql-replication-user': self.config['POSTGRESQL_REPLICATION_USER'],
                        'postgresql-replication-password': self.config['POSTGRESQL_REPLICATION_PASSWORD'],
                        'keycloak-user': self.config['KEYCLOAK_USER'],
                        'keycloak-password': self.config['KEYCLOAK_PASSWORD'],
                        'traefik-auth-users': f"traefikadmin:{self.generate_hashed_password(self.config['TRAEFIK_AUTH_PASSWORD'])}"
                    })
                if doc.get('kind') == 'ConfigMap' and doc.get('metadata', {}).get('name') == 'keycloak-config':
                    doc['data'].update({
                        'postgresql-database': self.config['POSTGRESQL_DATABASE'],
                        'db-vendor': self.config['DB_VENDOR'],
                        'db-addr': self.config['DB_ADDR'],
                        'jgroups-discovery-protocol': self.config['JGROUPS_DISCOVERY_PROTOCOL'],
                        'jgroups-discovery-properties': self.config['JGROUPS_DISCOVERY_PROPERTIES'],
                        'proxy-address-forwarding': self.config['PROXY_ADDRESS_FORWARDING'],
                        'keycloak-loglevel': self.config['KEYCLOAK_LOGLEVEL'],
                        'letsencrypt-email': self.config['LETSENCRYPT_EMAIL']
                    })
                    # Update traefik.yml in ConfigMap
                    traefik_yaml = yaml.safe_load(doc['data']['traefik.yml'])
                    traefik_yaml['certificatesResolvers']['letsencrypt']['acme']['email'] = self.config['LETSENCRYPT_EMAIL']
                    doc['data']['traefik.yml'] = yaml.safe_dump(traefik_yaml)

            with open(self.manifest_file, 'w') as f:
                yaml.safe_dump_all(manifest_list, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def apply_kubernetes_manifest(self) -> bool:
        """Apply Kubernetes manifest."""
        logger.info(f"Applying Kubernetes manifest {self.manifest_file}")
        if not os.path.exists(self.manifest_file):
            logger.error(f"Manifest file {self.manifest_file} not found")
            return False
        try:
            subprocess.run([self.kubectl, "apply", "-f", self.manifest_file], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply Kubernetes manifest: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def deploy_docker_compose(self) -> bool:
        """Deploy using podman-compose."""
        logger.info(f"Deploying with {self.compose_file}")
        if not os.path.exists(self.compose_file):
            logger.error(f"Compose file {self.compose_file} not found")
            return False
        try:
            env_content = "\n".join(f"{k}={v}" for k, v in self.config.items())
            with open(".env", "w") as f:
                f.write(env_content)
            subprocess.run([self.podman_compose, "-f", self.compose_file, "up", "-d"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to deploy with podman-compose: {e}")
            return False

    def generate_ansible_playbook(self) -> bool:
        """Generate Ansible playbook for deployment."""
        logger.info(f"Generating Ansible playbook {self.ansible_playbook_file}")
        playbook = [
            {
                'name': 'Deploy Keycloak infrastructure',
                'hosts': 'keycloak_nodes',
                'become': True,
                'tasks': [
                    {
                        'name': 'Ensure required packages are installed',
                        'package': {
                            'name': ['podman', 'podman-compose', 'python3'],
                            'state': 'present'
                        }
                    },
                    {
                        'name': 'Copy compose file',
                        'copy': {
                            'src': self.compose_file,
                            'dest': f'/opt/keycloak/{self.compose_file}',
                            'mode': '0644'
                        }
                    },
                    {
                        'name': 'Copy .env file',
                        'copy': {
                            'content': "\n".join(f"{k}={v}" for k, v in self.config.items()),
                            'dest': '/opt/keycloak/.env',
                            'mode': '0600'
                        }
                    },
                    {
                        'name': 'Deploy Keycloak with podman-compose',
                        'command': f'podman-compose -f /opt/keycloak/{self.compose_file} up -d',
                        'args': {
                            'chdir': '/opt/keycloak'
                        }
                    }
                ]
            }
        ]
        try:
            with open(self.ansible_playbook_file, 'w') as f:
                yaml.safe_dump(playbook, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error(f"Failed to generate Ansible playbook: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def run_ansible_playbook(self) -> bool:
        """Run Ansible playbook."""
        logger.info(f"Running Ansible playbook {self.ansible_playbook_file}")
        try:
            subprocess.run([self.ansible_playbook, self.ansible_playbook_file], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to run Ansible playbook: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def verify_deployment(self) -> bool:
        """Verify deployment status."""
        logger.info(f"Verifying deployment in namespace {self.namespace}")
        try:
            subprocess.run([self.kubectl, "get", "pods,svc,ingressroute", "-n", self.namespace], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to retrieve resources: {e}")
            return False

    def deploy(self, method: str = "kubernetes") -> bool:
        """Main deployment method."""
        logger.info(f"Starting Keycloak deployment using {method}")

        if not self.validate_config():
            return False
        if not self.check_requirements():
            return False

        if method == "kubernetes":
            if not all([
                self.install_traefik_crds(),
                self.install_cert_manager(),
                self.ensure_namespace(),
                self.update_manifest(),
                self.apply_kubernetes_manifest(),
                self.verify_deployment()
            ]):
                return False
        elif method == "docker":
            if not self.deploy_docker_compose():
                return False
        elif method == "ansible":
            if not all([
                self.generate_ansible_playbook(),
                self.run_ansible_playbook()
            ]):
                return False
        else:
            logger.error(f"Unknown deployment method: {method}")
            return False

        logger.info("Deployment completed successfully")
        return True

def load_config(args) -> Dict:
    """Load configuration from arguments or environment."""
    config = {
        'POSTGRESQL_USERNAME': args.postgresql_username or os.getenv('POSTGRESQL_USERNAME', 'keycloak'),
        'POSTGRESQL_PASSWORD': args.postgresql_password or os.getenv('POSTGRESQL_PASSWORD', 'keycloak_password'),
        'POSTGRESQL_DATABASE': args.postgresql_database or os.getenv('POSTGRESQL_DATABASE', 'keycloak'),
        'POSTGRESQL_REPLICATION_USER': args.postgresql_replication_user or os.getenv('POSTGRESQL_REPLICATION_USER', 'repl_user'),
        'POSTGRESQL_REPLICATION_PASSWORD': args.postgresql_replication_password or os.getenv('POSTGRESQL_REPLICATION_PASSWORD', 'repl_password'),
        'KEYCLOAK_USER': args.keycloak_user or os.getenv('KEYCLOAK_USER', 'admin'),
        'KEYCLOAK_PASSWORD': args.keycloak_password or os.getenv('KEYCLOAK_PASSWORD', 'admin_password'),
        'DB_VENDOR': args.db_vendor or os.getenv('DB_VENDOR', 'postgres'),
        'DB_ADDR': args.db_addr or os.getenv('DB_ADDR', 'postgres.keycloak.svc.cluster.local'),
        'JGROUPS_DISCOVERY_PROTOCOL': args.jgroups_discovery_protocol or os.getenv('JGROUPS_DISCOVERY_PROTOCOL', 'dns.DNS_PING'),
        'JGROUPS_DISCOVERY_PROPERTIES': args.jgroups_discovery_properties or os.getenv('JGROUPS_DISCOVERY_PROPERTIES', 'dns_query=keycloak.keycloak.svc.cluster.local'),
        'PROXY_ADDRESS_FORWARDING': args.proxy_address_forwarding or os.getenv('PROXY_ADDRESS_FORWARDING', 'true'),
        'KEYCLOAK_LOGLEVEL': args.keycloak_loglevel or os.getenv('KEYCLOAK_LOGLEVEL', 'INFO'),
        'TRAEFIK_AUTH_PASSWORD': args.traefik_auth_password or os.getenv('TRAEFIK_AUTH_PASSWORD', 'traefik_secure_password'),
        'LETSENCRYPT_EMAIL': args.letsencrypt_email or os.getenv('LETSENCRYPT_EMAIL', '')
    }
    return config

def main():
    parser = argparse.ArgumentParser(description="Keycloak Deployment Script")
    parser.add_argument("--method", choices=["kubernetes", "docker", "ansible"], default="kubernetes",
                        help="Deployment method")
    parser.add_argument("--namespace", default="keycloak", help="Kubernetes namespace")
    parser.add_argument("--postgresql-username", help="PostgreSQL username")
    parser.add_argument("--postgresql-password", help="PostgreSQL password")
    parser.add_argument("--postgresql-database", help="PostgreSQL database name")
    parser.add_argument("--postgresql-replication-user", help="PostgreSQL replication user")
    parser.add_argument("--postgresql-replication-password", help="PostgreSQL replication password")
    parser.add_argument("--keycloak-user", help="Keycloak admin user")
    parser.add_argument("--keycloak-password", help="Keycloak admin password")
    parser.add_argument("--db-vendor", help="Database vendor")
    parser.add_argument("--db-addr", help="Database address")
    parser.add_argument("--jgroups-discovery-protocol", help="JGroups discovery protocol")
    parser.add_argument("--jgroups-discovery-properties", help="JGroups discovery properties")
    parser.add_argument("--proxy-address-forwarding", help="Proxy address forwarding")
    parser.add_argument("--keycloak-loglevel", help="Keycloak log level")
    parser.add_argument("--traefik-auth-password", help="Traefik auth password")
    parser.add_argument("--letsencrypt-email", help="Let's Encrypt email for TLS certificates")

    args = parser.parse_args()

    config = load_config(args)
    deployer = KeycloakDeployer(config, args.namespace)

    try:
        if deployer.deploy(args.method):
            logger.info("Keycloak deployment completed successfully")
            return 0
        else:
            logger.error("Keycloak deployment failed")
            return 1
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())