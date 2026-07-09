import os
import yaml
import argparse
import logging
import subprocess
import shlex
import re
from pathlib import Path
from typing import Dict
from datetime import datetime
import jinja2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'haproxy_deployment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HAProxyDeployer:
    def __init__(self, config_file: str, dry_run: bool = False):
        self.config_file = config_file
        self.dry_run = dry_run
        self.config = self._load_config()
        self.project_dir = Path.cwd() / "haproxy_deployment"
        self.templates_dir = self.project_dir / "templates"
        self.config_dir = self.project_dir / "config"
        self.deployment_type = self.config.get('deployment_type', 'docker')
        self._setup_directories()

    def _setup_directories(self):
        self.project_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)

    def _load_config(self) -> Dict:
        default_config = {
            'deployment_type': 'docker',
            'haproxy_version': '3.0.8',
            'log_level': 'info',
            'socket_path': '/var/run/docker.sock',
            'replicas': 2,
            'ansible_inventory': 'inventory',
            'opensearch_host': 'opensearch',
            'opensearch_port': 9200,
            'maxconn': 10000,
            'fullconn': 5000,
            'domain': 'haproxy.example.com',
            'email': 'admin@example.com',
            'services': [
                {'name': 'default', 'backend': 'localhost', 'port': 8080, 'num_servers': 100}
            ]
        }
        if not os.path.exists(self.config_file):
            logger.warning(f"Configuration file {self.config_file} not found, using default configuration")
            return default_config
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
            config = {**default_config, **config}
            required_fields = ['deployment_type', 'haproxy_version']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required configuration field: {field}")
            if config['deployment_type'] not in ['docker', 'podman', 'kubernetes', 'ansible']:
                raise ValueError(f"Invalid deployment_type: {config['deployment_type']}")
            if not re.match(r'^\d+\.\d+\.\d+$', config['haproxy_version']):
                raise ValueError(f"Invalid haproxy_version format: {config['haproxy_version']}")
            if 'services' in config:
                if not isinstance(config['services'], list):
                    raise ValueError("Services must be a list")
                for service in config['services']:
                    if not all(key in service for key in ['name', 'backend', 'port']):
                        raise ValueError(f"Service {service.get('name', 'unknown')} missing required fields")
                    if not isinstance(service['port'], int) or service['port'] < 1 or service['port'] > 65535:
                        raise ValueError(f"Invalid port for service {service['name']}: {service['port']}")
                    if not re.match(r'^[a-zA-Z0-9_-]+$', service['name']):
                        raise ValueError(f"Invalid service name: {service['name']}")
                    if 'health_check' in service:
                        if not all(key in service['health_check'] for key in ['method', 'path']):
                            raise ValueError(f"Invalid health_check for service {service['name']}")
                        if service['health_check']['method'] not in ['GET', 'HEAD', 'OPTIONS']:
                            raise ValueError(f"Invalid health_check method for service {service['name']}")
                    if 'num_servers' in service and (not isinstance(service['num_servers'], int) or service['num_servers'] < 1):
                        raise ValueError(f"Invalid num_servers for service {service['name']}: {service['num_servers']}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}, falling back to default configuration")
            return default_config

    def _render_template(self, template_name: str, output_path: Path, context: Dict):
        if self.dry_run:
            logger.info(f"[DRY RUN] Would render template {template_name} to {output_path}")
            return
        try:
            template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.templates_dir))
            template = template_env.get_template(template_name)
            with open(output_path, 'w') as f:
                f.write(template.render(**context))
            logger.info(f"Rendered {template_name} to {output_path}")
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            raise

    def _generate_certificates(self):
        if self.dry_run:
            logger.info("[DRY RUN] Would generate certificates")
            return
        try:
            cert_script = self.project_dir / "generate-certs.sh"
            self._run_command(
                ['bash', str(cert_script)],
                "Generating SSL certificates"
            )
            if self.deployment_type == 'kubernetes':
                self._run_command(
                    ['kubectl', 'create', 'secret', 'generic', 'haproxy-certs',
                     '--from-file=haproxy.pem=/usr/local/etc/haproxy/certs/haproxy.pem',
                     '--from-file=server.key=/usr/local/etc/haproxy/certs/server.key'],
                    "Creating Kubernetes secret for certificates"
                )
        except Exception as e:
            logger.error(f"Certificate generation failed: {e}")
            raise

    def deploy_docker(self):
        container_manager = 'podman' if self.deployment_type == 'podman' else 'docker'
        try:
            self._render_template(
                "haproxy.cfg.j2",
                self.project_dir / "haproxy.cfg",
                {
                    'log_level': self.config.get('log_level', 'info'),
                    'services': self.config.get('services', []),
                    'maxconn': self.config.get('maxconn', 10000),
                    'fullconn': self.config.get('fullconn', 5000)
                }
            )
            self._render_template(
                "fluentd.conf.j2",
                self.project_dir / "fluentd.conf",
                {
                    'opensearch_host': self.config.get('opensearch_host', 'opensearch'),
                    'opensearch_port': self.config.get('opensearch_port', 9200)
                }
            )
            self._generate_certificates()
            self._run_command(
                [container_manager, 'images', '-q', f'haproxy:{self.config["haproxy_version"]}'],
                f"Checking if HAProxy {self.deployment_type} image exists"
            )
            self._run_command(
                [container_manager, 'build', '-t', f'haproxy:{self.config["haproxy_version"]}', str(self.project_dir)],
                f"Building HAProxy {self.deployment_type} image"
            )
            self._run_command(
                [container_manager, 'compose', '-f', str(self.project_dir / 'docker-compose.yml'), 'up', '-d'],
                f"Deploying HAProxy with {self.deployment_type}-compose"
            )
            logger.info(f"HAProxy deployed successfully using {self.deployment_type}")
        except Exception as e:
            logger.error(f"Deployment failed, rolling back...")
            self._run_command(
                [container_manager, 'compose', '-f', str(self.project_dir / 'docker-compose.yml'), 'down'],
                f"Cleaning up {self.deployment_type} containers"
            )
            logger.error(f"Failed to deploy HAProxy with {self.deployment_type}: {e}")
            raise

    def deploy_kubernetes(self):
        try:
            self._generate_certificates()
            k8s_templates = [
                ('haproxy-configmap.yaml.j2', 'haproxy-configmap.yaml'),
                ('haproxy-deployment.yaml.j2', 'haproxy-deployment.yaml'),
                ('haproxy-service.yaml.j2', 'haproxy-service.yaml'),
                ('haproxy-hpa.yaml.j2', 'haproxy-hpa.yaml'),
                ('haproxy-ingress.yaml.j2', 'haproxy-ingress.yaml'),
                ('haproxy-rbac.yaml.j2', 'haproxy-rbac.yaml'),
                ('haproxy-network-policy.yaml.j2', 'haproxy-network-policy.yaml'),
                ('haproxy-pod-security.yaml.j2', 'haproxy-pod-security.yaml'),
                ('logging-deployment.yaml.j2', 'logging-deployment.yaml')
            ]
            for template_name, output_name in k8s_templates:
                self._render_template(
                    template_name,
                    self.project_dir / output_name,
                    {
                        'haproxy_version': self.config['haproxy_version'],
                        'log_level': self.config.get('log_level', 'info'),
                        'services': self.config.get('services', []),
                        'replicas': self.config.get('replicas', 2),
                        'socket_path': self.config.get('socket_path', '/var/run/docker.sock'),
                        'opensearch_host': self.config.get('opensearch_host', 'opensearch'),
                        'opensearch_port': self.config.get('opensearch_port', 9200),
                        'maxconn': self.config.get('maxconn', 10000),
                        'fullconn': self.config.get('fullconn', 5000)
                    }
                )
            manifests = [
                'haproxy-rbac.yaml',
                'haproxy-pod-security.yaml',
                'haproxy-configmap.yaml',
                'haproxy-deployment.yaml',
                'haproxy-service.yaml',
                'haproxy-hpa.yaml',
                'haproxy-ingress.yaml',
                'haproxy-network-policy.yaml',
                'logging-deployment.yaml'
            ]
            for manifest in manifests:
                manifest_path = self.project_dir / manifest
                if not manifest_path.exists():
                    logger.error(f"Kubernetes manifest not found: {manifest_path}")
                    raise FileNotFoundError(f"Missing {manifest}")
                self._run_command(
                    ['kubectl', 'apply', '-f', str(manifest_path)],
                    f"Applying Kubernetes manifest: {manifest}"
                )
            logger.info("HAProxy deployed successfully on Kubernetes")
        except Exception as e:
            logger.error(f"Deployment failed, rolling back...")
            self._run_command(
                ['kubectl', 'delete', '-f', str(self.project_dir / 'haproxy-deployment.yaml')],
                "Cleaning up Kubernetes deployment"
            )
            logger.error(f"Failed to deploy HAProxy on Kubernetes: {e}")
            raise

    def deploy_ansible(self):
        try:
            playbook_path = self.project_dir / 'deploy_haproxy.yml'
            if not playbook_path.exists():
                logger.error(f"Ansible playbook not found: {playbook_path}")
                raise FileNotFoundError("Missing Ansible playbook")
            self._run_command(
                ['ansible-playbook', str(playbook_path), '-i', self.config.get('ansible_inventory', 'inventory')],
                "Running Ansible playbook for HAProxy deployment"
            )
            logger.info("HAProxy deployed successfully using Ansible")
        except Exception as e:
            logger.error(f"Failed to deploy HAProxy with Ansible: {e}")
            raise

    def _run_command(self, command: list, description: str) -> None:
        command = [shlex.quote(str(arg)) for arg in command]
        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {description} with command: {' '.join(command)}")
            return
        try:
            logger.info(f"Executing: {description}")
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                shell=True
            )
            logger.info(f"{description} completed successfully: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"{description} failed: {e.stderr}")
            raise

    def deploy(self):
        logger.info(f"Starting HAProxy deployment with {self.deployment_type}")
        try:
            if self.deployment_type in ['docker', 'podman']:
                self.deploy_docker()
            elif self.deployment_type == 'kubernetes':
                self.deploy_kubernetes()
            elif self.deployment_type == 'ansible':
                self.deploy_ansible()
            else:
                raise ValueError(f"Unsupported deployment type: {self.deployment_type}")
            logger.info("HAProxy deployment completed successfully")
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Deploy HAProxy with configurable options")
    parser.add_argument('--config', default='config.yml', help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Simulate deployment without executing commands')
    args = parser.parse_args()
    deployer = HAProxyDeployer(args.config, args.dry_run)
    deployer.deploy()

if __name__ == "__main__":
    main()