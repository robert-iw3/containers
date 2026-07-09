import argparse
import os
import subprocess
import yaml
import logging
import json
from pathlib import Path
from typing import Dict

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeploymentManager:
    def __init__(self, env_file='.env', deployment_type='docker', dry_run=False):
        self.env_file = env_file
        self.deployment_type = deployment_type
        self.dry_run = dry_run
        self.env_vars = self.load_env()
        self.validate_env()

    def load_env(self) -> Dict[str, str]:
        """Load environment variables from file."""
        env_vars = {}
        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value
                        os.environ[key] = value
            return env_vars
        except Exception as e:
            logger.error(f"Failed to load {self.env_file}: {e}")
            raise

    def validate_env(self):
        """Validate required environment variables."""
        required_vars = [
            'POSTGRES_PASSWORD', 'DEFGUARD_DEFAULT_ADMIN_PASSWORD', 'DEFGUARD_SECRET_KEY',
            'DEFGUARD_AUTH_SECRET', 'DEFGUARD_GATEWAY_SECRET', 'DEFGUARD_YUBIBRIDGE_SECRET',
            'DEFGUARD_TOKEN', 'DEFGUARD_TLS_CERT', 'DEFGUARD_TLS_KEY'
        ]
        missing = [var for var in required_vars if not self.env_vars.get(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        logger.info("Environment variables validated successfully.")

    def generate_certs(self):
        """Generate self-signed certificates for mTLS if not provided."""
        cert_dir = Path('certs')
        cert_dir.mkdir(exist_ok=True)
        cert_path = cert_dir / 'tls.crt'
        key_path = cert_dir / 'tls.key'
        if not cert_path.exists() or not key_path.exists():
            logger.info("Generating self-signed certificates for mTLS...")
            if not self.dry_run:
                subprocess.run([
                    'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-nodes',
                    '-out', str(cert_path), '-keyout', str(key_path),
                    '-days', '365', '-subj', '/CN=defguard'
                ], check=True)
        self.env_vars['DEFGUARD_TLS_CERT'] = str(cert_path)
        self.env_vars['DEFGUARD_TLS_KEY'] = str(key_path)

    def deploy_docker(self):
        """Deploy using Docker Compose."""
        try:
            if self.dry_run:
                logger.info("Dry run: Would execute docker-compose up")
                return
            subprocess.run(['docker', 'volume', 'create', 'certs'], check=True)
            subprocess.run(['docker', 'cp', self.env_vars['DEFGUARD_TLS_CERT'], 'certs:/certs/tls.crt'], check=True)
            subprocess.run(['docker', 'cp', self.env_vars['DEFGUARD_TLS_KEY'], 'certs:/certs/tls.key'], check=True)
            subprocess.run(['docker-compose', 'up', '-d', '--build', '--force-recreate'], check=True)
            logger.info("Docker Compose deployment completed.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker deployment failed: {e}")
            raise

    def deploy_podman(self):
        """Deploy using Podman Compose (rootless)."""
        try:
            if self.dry_run:
                logger.info("Dry run: Would execute podman-compose up")
                return
            subprocess.run(['podman', 'volume', 'create', 'certs'], check=True)
            subprocess.run(['podman', 'cp', self.env_vars['DEFGUARD_TLS_CERT'], 'certs:/certs/tls.crt'], check=True)
            subprocess.run(['podman', 'cp', self.env_vars['DEFGUARD_TLS_KEY'], 'certs:/certs/tls.key'], check=True)
            subprocess.run(['podman-compose', 'up', '-d', '--build'], check=True)
            logger.info("Podman Compose deployment completed.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Podman deployment failed: {e}")
            raise

    def deploy_kubernetes(self):
        """Deploy to Kubernetes."""
        try:
            if self.dry_run:
                logger.info("Dry run: Would apply Kubernetes manifests")
                return
            # Create secrets from environment variables
            secrets = {
                'POSTGRES_PASSWORD': self.env_vars['POSTGRES_PASSWORD'],
                'DEFGUARD_DEFAULT_ADMIN_PASSWORD': self.env_vars['DEFGUARD_DEFAULT_ADMIN_PASSWORD'],
                'DEFGUARD_SECRET_KEY': self.env_vars['DEFGUARD_SECRET_KEY'],
                'DEFGUARD_AUTH_SECRET': self.env_vars['DEFGUARD_AUTH_SECRET'],
                'DEFGUARD_GATEWAY_SECRET': self.env_vars['DEFGUARD_GATEWAY_SECRET'],
                'DEFGUARD_YUBIBRIDGE_SECRET': self.env_vars['DEFGUARD_YUBIBRIDGE_SECRET'],
                'DEFGUARD_TOKEN': self.env_vars['DEFGUARD_TOKEN']
            }
            with open('k8s/secrets.yml', 'w') as f:
                yaml.dump({
                    'apiVersion': 'v1',
                    'kind': 'Secret',
                    'metadata': {'name': 'defguard-secrets', 'namespace': 'defguard'},
                    'type': 'Opaque',
                    'data': {k: v.encode('utf-8').hex() for k, v in secrets.items()}
                }, f)
            # Copy certificates to Kubernetes secrets
            subprocess.run([
                'kubectl', 'create', 'secret', 'tls', 'defguard-tls', '--cert', self.env_vars['DEFGUARD_TLS_CERT'],
                '--key', self.env_vars['DEFGUARD_TLS_KEY'], '-n', 'defguard'
            ], check=True)
            # Apply manifests
            manifests = ['k8s/namespace.yml', 'k8s/secrets.yml', 'k8s/pvc.yml', 'k8s/deployment.yml', 'k8s/service.yml', 'k8s/network-policy.yml', 'k8s/hpa.yml']
            for manifest in manifests:
                subprocess.run(['kubectl', 'apply', '-f', manifest], check=True)
            logger.info("Kubernetes deployment completed.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Kubernetes deployment failed: {e}")
            raise

    def deploy_ansible(self):
        """Run Ansible playbook for configuration."""
        try:
            if self.dry_run:
                logger.info("Dry run: Would execute Ansible playbook")
                return
            subprocess.run(['ansible-playbook', 'ansible/deploy.yml', '-e', f'deployment_type={self.deployment_type}'], check=True)
            logger.info("Ansible configuration completed.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ansible configuration failed: {e}")
            raise

    def rollback(self):
        """Rollback deployment in case of failure."""
        logger.warning("Initiating rollback...")
        if self.deployment_type == 'docker':
            subprocess.run(['docker-compose', 'down', '-v'], check=True)
        elif self.deployment_type == 'podman':
            subprocess.run(['podman-compose', 'down', '-v'], check=True)
        elif self.deployment_type == 'kubernetes':
            subprocess.run(['kubectl', 'delete', 'namespace', 'defguard'], check=True)
        logger.info("Rollback completed.")

    def deploy(self):
        """Execute deployment based on specified type."""
        logger.info(f"Starting {self.deployment_type} deployment...")
        try:
            self.generate_certs()
            if self.deployment_type == 'docker':
                self.deploy_docker()
            elif self.deployment_type == 'podman':
                self.deploy_podman()
            elif self.deployment_type == 'kubernetes':
                self.deploy_kubernetes()
            self.deploy_ansible()
            logger.info("Deployment completed successfully.")
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self.rollback()
            raise

def main():
    parser = argparse.ArgumentParser(description="Defguard Production Deployment Script")
    parser.add_argument('--type', choices=['docker', 'podman', 'kubernetes'], default='docker',
                        help="Deployment type")
    parser.add_argument('--env', default='.env', help="Path to environment file")
    parser.add_argument('--dry-run', action='store_true', help="Perform a dry run without executing commands")
    args = parser.parse_args()

    manager = DeploymentManager(env_file=args.env, deployment_type=args.type, dry_run=args.dry_run)
    manager.deploy()

if __name__ == "__main__":
    main()