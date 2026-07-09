import os
import subprocess
import yaml
import argparse
import logging
import shutil
import sys
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
import uuid
import socket
import psutil
from pydantic import BaseModel, validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zeek_deployment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Pydantic models for configuration validation
class ZeekConfig(BaseModel):
    version: str
    interface: str
    log_dir: str
    spool_dir: str
    worker_processes: int
    network_mode: str
    cluster: Optional[Dict] = None

    @validator('worker_processes')
    def validate_workers(cls, v):
        max_cores = psutil.cpu_count() or 4
        return min(v, max_cores)

class SecurityConfig(BaseModel):
    restrict_filters: str
    disable_ssl_validation: bool
    enable_json_logs: bool
    disable_password_logging: bool = True

class SplunkConfig(BaseModel):
    enabled: bool
    hec_url: str
    hec_token: str

class ElasticsearchConfig(BaseModel):
    enabled: bool
    host: str
    index: str

class DeploymentConfig(BaseModel):
    method: str
    namespace: str
    container_name: str

class Config(BaseModel):
    zeek: ZeekConfig
    security: SecurityConfig
    splunk: SplunkConfig
    elasticsearch: ElasticsearchConfig
    deployment: DeploymentConfig

class ZeekDeployer:
    def __init__(self, config_path: str = "deploy_config.yaml"):
        self.config_path = config_path
        self.base_dir = Path.cwd()
        self.config = self.load_config()
        self.deployment_id = str(uuid.uuid4())
        self.deployment_timestamp = datetime.now().isoformat()
        self.config_files = {
            'local.zeek': 'share/zeek/site/local.zeek',
            'login.zeek': 'share/zeek/site/login.zeek',
            'known-routers.zeek': 'share/zeek/site/known-routers.zeek',
            'guess.zeek': 'share/zeek/site/guess.zeek',
            'guess_ics_map.txt': 'share/zeek/site/guess_ics_map.txt',
            'networks.cfg': 'etc/networks.cfg',
            'zeekctl.cfg': 'etc/zeekctl.cfg',
            'node.cfg': 'etc/node.cfg',
            'docker-compose.yml': 'docker-compose.yml',
            'Dockerfile': 'Dockerfile',
            'entrypoint.sh': 'entrypoint.sh',
            'prometheus.yml': 'prometheus.yml',
            'zeek_exporter.py': 'zeek_exporter.py',
            'zeek_connector.py': 'zeek_connector.py',
            'Dockerfile.connector': 'Dockerfile.connector'
        }

    def load_config(self) -> Dict:
        """Load and validate deployment configuration from YAML file."""
        default_config = {
            'zeek': {
                'version': '8.0.4',
                'interface': 'eth0',
                'log_dir': '/var/log/zeek',
                'spool_dir': '/var/spool/zeek',
                'worker_processes': psutil.cpu_count() or 4,
                'network_mode': 'host',
                'cluster': {'enabled': False}
            },
            'security': {
                'restrict_filters': 'tcp port 80 or tcp port 443',
                'disable_ssl_validation': False,
                'enable_json_logs': True,
                'disable_password_logging': True
            },
            'splunk': {
                'enabled': False,
                'hec_url': 'https://your-splunk-host:8088/services/collector/event',
                'hec_token': 'your-splunk-hec-token'
            },
            'elasticsearch': {
                'enabled': False,
                'host': 'http://localhost:9200',
                'index': 'zeek-logs'
            },
            'deployment': {
                'method': 'docker',
                'namespace': 'zeek',
                'container_name': 'zeek-monitor'
            }
        }

        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                default_config.update(config)
                Config(**default_config)  # Validate with Pydantic
                logger.info("Loaded and validated configuration from %s", self.config_path)
            else:
                logger.warning("No config file found, using defaults")
            return default_config
        except Exception as e:
            logger.error("Failed to load or validate config: %s", str(e))
            sys.exit(1)

    def ensure_directories(self) -> None:
        """Create necessary directories with secure permissions."""
        dirs = [
            self.config['zeek']['log_dir'],
            self.config['zeek']['spool_dir'],
            f"{self.base_dir}/etc",
            f"{self.base_dir}/share/zeek/site",
            f"{self.base_dir}/backup"
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o750)
            if os.geteuid() == 0:
                os.chown(d, 0, 0)
            logger.info("Created/verified directory: %s", d)

    def backup_configs(self) -> None:
        """Backup existing configuration files before deployment."""
        backup_dir = f"{self.base_dir}/backup/{self.deployment_timestamp}"
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        for src, dst in self.config_files.items():
            if os.path.exists(dst):
                shutil.copy(dst, f"{backup_dir}/{os.path.basename(dst)}")
                logger.info("Backed up %s to %s", dst, backup_dir)

    def check_requirements(self) -> bool:
        """Verify required tools are installed."""
        requirements = {
            'docker': ['docker', '--version'],
            'podman': ['podman', '--version'],
            'kubectl': ['kubectl', 'version', '--client'],
            'ansible': ['ansible', '--version']
        }

        method = self.config['deployment']['method']
        try:
            subprocess.run(
                requirements[method],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("%s is installed and accessible", method)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Required tool %s not found", method)
            return False

    def copy_config_files(self) -> None:
        """Copy configuration files to appropriate locations."""
        self.backup_configs()
        for src, dst in self.config_files.items():
            try:
                shutil.copy(src, f"{self.base_dir}/{dst}")
                os.chmod(f"{self.base_dir}/{dst}", 0o644)
                logger.info("Copied %s to %s", src, dst)
            except Exception as e:
                logger.error("Failed to copy %s: %s", src, str(e))
                raise

    def deploy_docker(self) -> bool:
        """Deploy Zeek using Docker."""
        try:
            logger.info("Starting Docker deployment")
            cmd = [
                'docker-compose',
                '-f', f"{self.base_dir}/docker-compose.yml",
                'up', '-d', '--build'
            ]
            subprocess.run(cmd, check=True)
            logger.info("Docker deployment successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Docker deployment failed: %s", str(e))
            self.cleanup()
            return False

    def deploy_podman(self) -> bool:
        """Deploy Zeek using Podman."""
        try:
            logger.info("Starting Podman deployment")
            cmd = [
                'podman-compose',
                '-f', f"{self.base_dir}/docker-compose.yml",
                'up', '-d', '--build'
            ]
            subprocess.run(cmd, check=True)
            logger.info("Podman deployment successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Podman deployment failed: %s", str(e))
            self.cleanup()
            return False

    def deploy_kubernetes(self) -> bool:
        """Deploy Zeek using Kubernetes."""
        try:
            logger.info("Starting Kubernetes deployment")
            k8s_manifest = {
                'apiVersion': 'v1',
                'kind': 'Pod',
                'metadata': {
                    'name': self.config['deployment']['container_name'],
                    'namespace': self.config['deployment']['namespace']
                },
                'spec': {
                    'hostNetwork': True,
                    'containers': [{
                        'name': 'zeek',
                        'image': f"zeek:{self.config['zeek']['version']}",
                        'securityContext': {
                            'privileged': True,
                            'capabilities': {
                                'add': ['NET_RAW', 'NET_ADMIN']
                            }
                        },
                        'resources': {
                            'limits': {
                                'cpu': '2',
                                'memory': '4Gi'
                            }
                        },
                        'volumeMounts': [
                            {
                                'name': 'logs',
                                'mountPath': '/usr/local/zeek/logs'
                            },
                            {
                                'name': 'config',
                                'mountPath': '/usr/local/zeek/etc'
                            }
                        ]
                    }, {
                        'name': 'zeek-exporter',
                        'image': f"zeek:{self.config['zeek']['version']}",
                        'command': ['python3', '/usr/local/zeek/bin/zeek_exporter.py'],
                        'ports': [{'containerPort': 9911}],
                        'volumeMounts': [{
                            'name': 'logs',
                            'mountPath': '/usr/local/zeek/logs'
                        }]
                    }, {
                        'name': 'zeek-connector',
                        'image': 'zeek-connector:latest',
                        'env': [
                            {'name': 'ZEEK_LOG_DIR', 'value': '/usr/local/zeek/logs'},
                            {'name': 'SPLUNK_ENABLED', 'value': str(self.config['splunk']['enabled']).lower()},
                            {'name': 'SPLUNK_HEC_URL', 'value': self.config['splunk']['hec_url']},
                            {'name': 'SPLUNK_TOKEN', 'value': self.config['splunk']['hec_token']},
                            {'name': 'ES_ENABLED', 'value': str(self.config['elasticsearch']['enabled']).lower()},
                            {'name': 'ES_HOST', 'value': self.config['elasticsearch']['host']},
                            {'name': 'ES_INDEX', 'value': self.config['elasticsearch']['index']}
                        ],
                        'volumeMounts': [{
                            'name': 'logs',
                            'mountPath': '/usr/local/zeek/logs'
                        }]
                    }, {
                        'name': 'prometheus',
                        'image': 'prom/prometheus:latest',
                        'ports': [{'containerPort': 9090}],
                        'volumeMounts': [{
                            'name': 'prometheus-config',
                            'mountPath': '/etc/prometheus'
                        }]
                    }],
                    'volumes': [
                        {
                            'name': 'logs',
                            'hostPath': {
                                'path': self.config['zeek']['log_dir']
                            }
                        },
                        {
                            'name': 'config',
                            'hostPath': {
                                'path': f"{self.base_dir}/etc"
                            }
                        },
                        {
                            'name': 'prometheus-config',
                            'hostPath': {
                                'path': f"{self.base_dir}/prometheus.yml"
                            }
                        }
                    ]
                }
            }

            with open('zeek_k8s.yaml', 'w') as f:
                yaml.dump(k8s_manifest, f)

            subprocess.run(['kubectl', 'apply', '-f', 'zeek_k8s.yaml'], check=True)
            logger.info("Kubernetes deployment successful")
            return True
        except Exception as e:
            logger.error("Kubernetes deployment failed: %s", str(e))
            self.cleanup()
            return False

    def deploy_ansible(self) -> bool:
        """Deploy Zeek using Ansible."""
        try:
            logger.info("Starting Ansible deployment")
            ansible_playbook = {
                'name': 'Deploy Zeek',
                'hosts': 'localhost',
                'become': True,
                'tasks': [
                    {
                        'name': 'Ensure Zeek directories',
                        'file': {
                            'path': '{{ item }}',
                            'state': 'directory',
                            'mode': '0750'
                        },
                        'loop': [
                            self.config['zeek']['log_dir'],
                            self.config['zeek']['spool_dir'],
                            f"{self.base_dir}/etc",
                            f"{self.base_dir}/share/zeek/site",
                            f"{self.base_dir}/backup"
                        ]
                    },
                    {
                        'name': 'Copy Zeek config files',
                        'copy': {
                            'src': f"{self.base_dir}/{{ item.src }}",
                            'dest': f"{self.base_dir}/{{ item.dest }}",
                            'mode': '0644'
                        },
                        'loop': [
                            {'src': k, 'dest': v} for k, v in self.config_files.items()
                        ]
                    },
                    {
                        'name': 'Run Docker Compose',
                        'community.docker.docker_compose': {
                            'project_src': str(self.base_dir),
                            'files': ['docker-compose.yml'],
                            'state': 'present',
                            'build': True
                        }
                    }
                ]
            }

            with open('zeek_playbook.yml', 'w') as f:
                yaml.dump([ansible_playbook], f)

            subprocess.run(['ansible-playbook', 'zeek_playbook.yml'], check=True)
            logger.info("Ansible deployment successful")
            return True
        except Exception as e:
            logger.error("Ansible deployment failed: %s", str(e))
            self.cleanup()
            return False

    def deploy(self) -> bool:
        """Execute the deployment based on configured method."""
        if not self.check_requirements():
            return False

        self.ensure_directories()
        self.copy_config_files()

        method = self.config['deployment']['method']
        deployment_methods = {
            'docker': self.deploy_docker,
            'podman': self.deploy_podman,
            'kubernetes': self.deploy_kubernetes,
            'ansible': self.deploy_ansible
        }

        if method not in deployment_methods:
            logger.error("Unsupported deployment method: %s", method)
            return False

        return deployment_methods[method]()

    def cleanup(self) -> None:
        """Clean up deployment artifacts."""
        try:
            method = self.config['deployment']['method']
            if method in ['docker', 'podman']:
                subprocess.run(['docker-compose', 'down'], check=True)
            elif method == 'kubernetes':
                subprocess.run(['kubectl', 'delete', '-f', 'zeek_k8s.yaml'], check=True)
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.warning("Cleanup failed: %s", str(e))

def main():
    parser = argparse.ArgumentParser(description='Deploy Zeek network monitoring')
    parser.add_argument('--config', default='deploy_config.yaml', help='Path to configuration file')
    parser.add_argument('--cleanup', action='store_true', help='Clean up deployment')
    args = parser.parse_args()

    deployer = ZeekDeployer(args.config)

    if args.cleanup:
        deployer.cleanup()
    else:
        success = deployer.deploy()
        if success:
            logger.info("Zeek deployment completed successfully")
        else:
            logger.error("Zeek deployment failed")
            sys.exit(1)

if __name__ == '__main__':
    main()