import os
import subprocess
import argparse
import logging
import yaml
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import psycopg2
from psycopg2 import OperationalError
import kubernetes.client
from kubernetes import config
import ansible_runner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deploy_stack.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GrafanaLokiStack:
    def __init__(self, config_file: str = "config.yml"):
        self.config_file = config_file
        self.config = self.load_config()
        self.deployment_type = self.config.get('deployment_type', 'docker')
        self.container_engine = 'docker' if self.deployment_type == 'docker' else 'podman'
        self.kube_client = None
        self.base_dir = Path(__file__).parent
        self.env_vars = self.load_env_vars()
        self.check_required_env()
        self.render_templates()

    def load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
                logger.info("Configuration loaded successfully from %s", self.config_file)
                return config
        except Exception as e:
            logger.error("Failed to load configuration: %s", e)
            raise

    def load_env_vars(self) -> Dict:
        """Load environment variables from .env file."""
        env_vars = {}
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value.strip("'").strip('"')
            logger.info("Environment variables loaded successfully")
        except Exception as e:
            logger.error("Failed to load .env file: %s", e)
            raise
        return env_vars

    def check_required_env(self):
        """Check for required environment variables."""
        required = [
            'LDAP_HOST', 'LDAP_BIND_DN', 'LDAP_BIND_PASSWORD', 'LDAP_SEARCH_BASE_DNS',
            'LDAP_ADMIN_GROUP', 'LDAP_EDITOR_GROUP', 'LDAP_VIEWER_GROUP',
            'POSTGRESQL_USERNAME', 'POSTGRESQL_PASSWORD', 'POSTGRESQL_DATABASE',
            'POSTGRESQL_REPLICATION_USER', 'POSTGRESQL_REPLICATION_PASSWORD',
            'GF_SERVER_DOMAIN', 'GF_SERVER_ROOT_URL', 'GF_SECURITY_ADMIN_USER',
            'GF_SECURITY_ADMIN_PASSWORD', 'GF_SMTP_HOST', 'GF_SMTP_USER',
            'GF_SMTP_PASSWORD', 'GF_SMTP_FROM_ADDRESS', 'WALLARM_API_HOST',
            'WALLARM_API_TOKEN', 'TRAEFIK_ACME_EMAIL', 'TRAEFIK_DASHBOARD_DOMAIN',
            'TRAEFIK_AUTH_USERS'
        ]
        missing = [r for r in required if r not in self.env_vars]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    def render_templates(self):
        """Render configuration files with environment variables."""
        files_to_render = ['ldap.toml']
        for file_path in files_to_render:
            full_path = self.base_dir / file_path
            if full_path.exists():
                with open(full_path, 'r') as f:
                    content = f.read()
                for k, v in self.env_vars.items():
                    content = content.replace('${' + k + '}', v)
                with open(full_path, 'w') as f:
                    f.write(content)
                logger.info("Rendered %s with environment variables", file_path)

    def setup_kubernetes_client(self):
        """Initialize Kubernetes client."""
        try:
            config.load_kube_config()
            self.kube_client = kubernetes.client.CoreV1Api()
            logger.info("Kubernetes client initialized")
        except Exception as e:
            logger.error("Failed to initialize Kubernetes client: %s", e)
            raise

    def deploy_docker(self):
        """Deploy stack using Docker or Podman."""
        logger.info("Starting deployment with %s", self.container_engine)
        compose_files = [
            "docker-prometheus.yml",
            "docker-compose-grafana.yml",
            "docker-loki.yml",
            "wallarm-node.yml"
        ]
        try:
            for compose_file in compose_files:
                subprocess.run([self.container_engine, "compose", "-f", compose_file, "up", "-d"], check=True, env=os.environ.update(self.env_vars))
            logger.info("Deployment completed successfully with %s", self.container_engine)
        except subprocess.CalledProcessError as e:
            logger.error("Deployment failed: %s", e)
            raise

    def deploy_kubernetes(self):
        """Deploy stack using Kubernetes."""
        if not self.kube_client:
            self.setup_kubernetes_client()

        logger.info("Starting Kubernetes deployment")
        compose_files = [
            "docker-compose-grafana.yml",
            "docker-prometheus.yml",
            "docker-loki.yml",
            "wallarm-node.yml"
        ]
        try:
            os.makedirs("k8s", exist_ok=True)
            for compose_file in compose_files:
                subprocess.run(["kompose", "convert", "-f", compose_file, "-o", "k8s/"], check=True)

            for manifest in self.base_dir.joinpath("k8s").glob("*.yaml"):
                subprocess.run(["kubectl", "apply", "-f", str(manifest)], check=True)
            logger.info("Kubernetes deployment completed")
        except Exception as e:
            logger.error("Kubernetes deployment failed: %s", e)
            raise

    def deploy_ansible(self):
        """Deploy stack using Ansible."""
        logger.info("Starting Ansible deployment")
        try:
            ansible_runner.run(
                private_data_dir='./ansible',
                playbook='deploy_grafana_loki.yml',
                extravars=self.env_vars
            )
            logger.info("Ansible deployment completed")
        except Exception as e:
            logger.error("Ansible deployment failed: %s", e)
            raise

    def restore_database(self, backup_file: str):
        """Restore PostgreSQL database from backup."""
        logger.info("Starting database restore for backup: %s", backup_file)
        try:
            # Stop Grafana service
            logger.info("Stopping Grafana service")
            subprocess.run([self.container_engine, "stop", "grafana"], check=True)

            # Connect to PostgreSQL and drop/create database
            conn = psycopg2.connect(
                host="postgres-grafana.io",
                port=5432,
                database="postgres",  # Connect to default db to drop target
                user=self.env_vars['POSTGRESQL_USERNAME'],
                password=self.env_vars['POSTGRESQL_PASSWORD']
            )
            conn.set_session(autocommit=True)
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS {self.env_vars['POSTGRESQL_DATABASE']}")
            cursor.execute(f"CREATE DATABASE {self.env_vars['POSTGRESQL_DATABASE']}")
            cursor.close()
            conn.close()

            # Restore database
            restore_cmd = (
                f'gunzip -c /srv/grafana-postgres/backups/{backup_file} | '
                f'psql -h postgres-grafana.io -p 5432 '
                f'-U {self.env_vars["POSTGRESQL_USERNAME"]} '
                f'{self.env_vars["POSTGRESQL_DATABASE"]}'
            )
            env = os.environ.copy()
            env['PGPASSWORD'] = self.env_vars['POSTGRESQL_PASSWORD']
            subprocess.run(
                [self.container_engine, 'exec', 'psql-backup', 'sh', '-c', restore_cmd],
                check=True,
                env=env
            )

            # Start Grafana service
            logger.info("Starting Grafana service")
            subprocess.run([self.container_engine, "start", "grafana"], check=True)
            logger.info("Database restore completed successfully")
        except Exception as e:
            logger.error("Database restore failed: %s", e)
            raise
        finally:
            # Ensure service is restarted even on failure
            subprocess.run([self.container_engine, "start", "grafana"], check=False)

    def list_backups(self) -> List[str]:
        """List available database backups."""
        try:
            cmd = [self.container_engine, 'exec', 'psql-backup', 'sh', '-c', 'ls /srv/grafana-postgres/backups/']
            result = subprocess.run(cmd, capture_output=True, check=True)
            backups = result.stdout.decode().split()
            logger.info("Available backups: %s", backups)
            return backups
        except Exception as e:
            logger.error("Failed to list backups: %s", e)
            raise

    def generate_env_template(self):
        """Generate .env template."""
        template = """
LDAP_HOST=your-ldap-server
LDAP_BIND_DN=enter@bind.com
LDAP_BIND_PASSWORD=YourPassword
LDAP_SEARCH_BASE_DNS=OU=Users,DC=domain,DC=net
LDAP_ADMIN_GROUP=CN=Grafana-Admin,OU=Groups,DC=domain,DC=net
LDAP_EDITOR_GROUP=CN=Grafana-Editor,OU=Groups,DC=domain,DC=net
LDAP_VIEWER_GROUP=CN=Grafana-Viewer,OU=Groups,DC=domain,DC=net
POSTGRESQL_USERNAME=grafana
POSTGRESQL_PASSWORD=securepassword
POSTGRESQL_DATABASE=grafana
POSTGRESQL_REPLICATION_USER=repl_user
POSTGRESQL_REPLICATION_PASSWORD=repl_password
GF_SERVER_DOMAIN=grafana.io
GF_SERVER_ROOT_URL=https://grafana.io
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=securepassword
GF_SMTP_HOST=smtp.example.com
GF_SMTP_USER=user@example.com
GF_SMTP_PASSWORD=smtppassword
GF_SMTP_FROM_ADDRESS=noreply@grafana.io
WALLARM_API_HOST=api.wallarm.com
WALLARM_API_TOKEN=your-token
TRAEFIK_ACME_EMAIL=your@email.com
TRAEFIK_DASHBOARD_DOMAIN=traefik.yourdomain.com
TRAEFIK_AUTH_USERS=traefikadmin:$apr1$encodedpassword  # Use htpasswd to generate
"""
        print(template)

    def deploy(self):
        """Deploy the stack based on configuration."""
        logger.info("Deploying Grafana/Loki stack with %s", self.deployment_type)

        if self.deployment_type in ['docker', 'podman']:
            self.deploy_docker()
        elif self.deployment_type == 'kubernetes':
            self.deploy_kubernetes()
        elif self.deployment_type == 'ansible':
            self.deploy_ansible()
        else:
            raise ValueError(f"Unsupported deployment type: {self.deployment_type}")

def main():
    parser = argparse.ArgumentParser(description="Deploy Grafana/Loki stack")
    parser.add_argument('--config', default='config.yml', help='Configuration file path')
    parser.add_argument('--deploy-type', choices=['docker', 'podman', 'kubernetes', 'ansible'],
                        help='Deployment type')
    parser.add_argument('--restore', help='Restore database from specified backup file')
    parser.add_argument('--list-backups', action='store_true', help='List available database backups')
    parser.add_argument('--generate-env-template', action='store_true', help='Generate .env template')

    args = parser.parse_args()

    stack = GrafanaLokiStack(args.config)

    if args.deploy_type:
        stack.config['deployment_type'] = args.deploy_type
        stack.deployment_type = args.deploy_type
        stack.container_engine = 'docker' if args.deploy_type == 'docker' else 'podman'

    if args.generate_env_template:
        stack.generate_env_template()
    elif args.list_backups:
        backups = stack.list_backups()
        print("Available backups:")
        for backup in backups:
            print(backup)
    elif args.restore:
        stack.restore_database(args.restore)
    else:
        stack.deploy()

if __name__ == "__main__":
    main()