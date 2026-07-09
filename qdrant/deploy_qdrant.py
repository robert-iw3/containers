import os
import yaml
import argparse
import subprocess
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'deployment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QdrantDeployer:
    def __init__(self, config_path: str):
        """Initialize deployer with configuration file."""
        self.config = self.load_config(config_path)
        self.base_dir = os.path.dirname(os.path.abspath(config_path))
        self.ansible_inventory = os.path.join(self.base_dir, 'inventory.yml')
        self.ansible_playbook = os.path.join(self.base_dir, 'deploy_qdrant.yml')

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load deployment configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
            raise

    def read_template(self, filename: str) -> str:
        """Read a template file's raw text from this script's own directory."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(script_dir, filename), 'r') as f:
            return f.read()

    def generate_inventory(self) -> None:
        """Generate Ansible inventory file."""
        inventory = {
            'all': {
                'hosts': {
                    host['name']: {
                        'ansible_host': host['ip'],
                        'ansible_user': host.get('user', 'ansible'),
                        'ansible_ssh_private_key_file': host.get('ssh_key', '~/.ssh/id_rsa')
                    } for host in self.config.get('hosts', [])
                }
            }
        }

        with open(self.ansible_inventory, 'w') as f:
            yaml.safe_dump(inventory, f)
        logger.info(f"Generated Ansible inventory at {self.ansible_inventory}")

    def generate_playbook(self) -> None:
        """Generate Ansible playbook for deployment."""
        playbook = [
            {
                'name': 'Deploy Qdrant with Kafka integration',
                'hosts': 'all',
                'become': True,
                'vars': {
                    'qdrant_version': self.config.get('qdrant_version', 'latest'),
                    'kafka_version': self.config.get('kafka_version', 'latest-ubi8'),
                    'data_dir': self.config.get('data_dir', '/opt/qdrant'),
                    'tls_enabled': self.config.get('tls_enabled', True),
                    'api_key': self.config.get('api_key', os.urandom(32).hex()),
                    'docker_compose_content': self.read_template('docker-compose.yml.j2'),
                    'qdrant_config_content': self.read_template('config.yaml.j2')
                },
                'tasks': [
                    {
                        'name': 'Install required packages',
                        'package': {
                            'name': ['podman', 'git', 'openssl'],
                            'state': 'present'
                        }
                    },
                    {
                        'name': 'Create data directories',
                        'file': {
                            'path': '{{ item }}',
                            'state': 'directory',
                            'mode': '0750',
                            'owner': 'qdrant',
                            'group': 'qdrant'
                        },
                        'loop': [
                            '{{ data_dir }}/qdrant_data',
                            '{{ data_dir }}/prometheus',
                            '{{ data_dir }}/grafana',
                            '{{ data_dir }}/tls'
                        ]
                    },
                    {
                        'name': 'Generate TLS certificates',
                        'when': 'tls_enabled',
                        'command': 'openssl req -x509 -newkey rsa:4096 -nodes -out {{ data_dir }}/tls/cert.pem -keyout {{ data_dir }}/tls/key.pem -days 365 -subj "/CN=qdrant.local"',
                        'args': {
                            'creates': '{{ data_dir }}/tls/cert.pem'
                        }
                    },
                    {
                        'name': 'Copy docker-compose configuration',
                        'copy': {
                            'content': '{{ docker_compose_content }}',
                            'dest': '{{ data_dir }}/docker-compose.yml',
                            'mode': '0640'
                        }
                    },
                    {
                        'name': 'Copy Qdrant configuration',
                        'copy': {
                            'content': '{{ qdrant_config_content }}',
                            'dest': '{{ data_dir }}/config.yaml',
                            'mode': '0640'
                        }
                    },
                    {
                        'name': 'Deploy containers with podman-compose',
                        'command': 'podman-compose -f {{ data_dir }}/docker-compose.yml up -d',
                        'args': {
                            'chdir': '{{ data_dir }}'
                        }
                    },
                    {
                        'name': 'Setup firewall rules',
                        'firewalld': {
                            'port': '{{ item }}',
                            'permanent': True,
                            'state': 'enabled',
                            'immediate': True
                        },
                        'loop': ['6333/tcp', '6334/tcp', '9092/tcp', '9090/tcp', '3000/tcp']
                    }
                ]
            }
        ]

        with open(self.ansible_playbook, 'w') as f:
            yaml.safe_dump(playbook, f)
        logger.info(f"Generated Ansible playbook at {self.ansible_playbook}")

    def deploy(self) -> None:
        """Execute the deployment process."""
        try:
            self.generate_inventory()
            self.generate_playbook()

            cmd = [
                'ansible-playbook',
                '-i', self.ansible_inventory,
                self.ansible_playbook
            ]

            logger.info("Starting deployment...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Deployment completed successfully:\n{result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during deployment: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Deploy Qdrant with Kafka integration')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    args = parser.parse_args()

    deployer = QdrantDeployer(args.config)
    deployer.deploy()

if __name__ == '__main__':
    main()