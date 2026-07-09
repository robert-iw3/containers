import subprocess
import os
import yaml
import logging
import json
from typing import Dict, Optional
import argparse
from distutils.spawn import find_executable

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FreeIPADeployer:
    def __init__(self, config_path: str, deployment_type: str = "docker"):
        """Initialize FreeIPA Deployer with configuration and deployment type"""
        self.deployment_type = deployment_type.lower()
        self.config = self._load_config(config_path)
        self._validate_config()
        self.domain = self.config['domain']
        self.realm = self.config['realm']
        self.admin_password = self.config['admin_password']
        self.dm_password = self.config['dm_password']
        self.data_dir = self.config.get('data_dir', '/var/lib/ipa-data')

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise ValueError(f"Config file error: {e}")

    def _validate_config(self):
        """Validate configuration file"""
        required_fields = ['domain', 'realm', 'admin_password', 'dm_password']
        for field in required_fields:
            if field not in self.config or not self.config[field]:
                raise ValueError(f"Missing or empty required config field: {field}")
        if not self.config['domain'].lower() == self.config['realm'].lower():
            logger.warning("Domain and realm should typically match in case")

    def _ensure_data_dir(self):
        """Create and secure data directory"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            subprocess.run(['chown', 'root:root', self.data_dir], check=True)
            subprocess.run(['chmod', '700', self.data_dir], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup data directory: {e}")
            raise

    def _check_runtime(self, runtime: str) -> bool:
        """Check if container runtime is available"""
        return bool(find_executable(runtime))

    def _cleanup_failed_deployment(self, container_name: str):
        """Clean up failed container deployment"""
        try:
            subprocess.run([self.deployment_type, 'rm', '-f', container_name], check=False)
        except subprocess.CalledProcessError:
            pass

    def deploy_docker(self):
        """Deploy FreeIPA using Docker"""
        if not self._check_runtime('docker'):
            raise RuntimeError("Docker runtime not found")

        container_name = 'freeipa-server-container'
        try:
            self._ensure_data_dir()
            cmd = [
                'docker', 'run', '-d',
                '--name', container_name,
                '-h', f'ipa.{self.domain}',
                '--read-only',
                '-v', f'{self.data_dir}:/data:Z',
                '-e', f'PASSWORD={self.admin_password}',
                '-p', '53:53/udp', '-p', '53:53',
                '-p', '80:80', '-p', '443:443',
                '-p', '389:389', '-p', '636:636',
                '-p', '88:88', '-p', '464:464',
                '-p', '88:88/udp', '-p', '464:464/udp',
                '-p', '123:123/udp',
                '--sysctl', 'net.ipv6.conf.all.disable_ipv6=0',
                '--dns', '127.0.0.1',
                'quay.io/freeipa/freeipa-server:almalinux-10',
                'ipa-server-install', '-U',
                '-r', self.realm,
                '--setup-dns',
                '--auto-forwarders',
                '--no-ntp',
                '--skip-mem-check'
            ]
            subprocess.run(cmd, check=True)
            logger.info("FreeIPA Docker container deployed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker deployment failed: {e}")
            self._cleanup_failed_deployment(container_name)
            raise

    def deploy_podman(self):
        """Deploy FreeIPA using Podman"""
        if not self._check_runtime('podman'):
            raise RuntimeError("Podman runtime not found")

        container_name = 'freeipa-server-container'
        try:
            self._ensure_data_dir()
            cmd = [
                'podman', 'run', '-d',
                '--name', container_name,
                '-h', f'ipa.{self.domain}',
                '--read-only',
                '-v', f'{self.data_dir}:/data:Z',
                '-e', f'PASSWORD={self.admin_password}',
                '-p', '53:53/udp', '-p', '53:53',
                '-p', '80:80', '-p', '443:443',
                '-p', '389:389', '-p', '636:636',
                '-p', '88:88', '-p', '464:464',
                '-p', '88:88/udp', '-p', '464:464/udp',
                '-p', '123:123/udp',
                '--sysctl', 'net.ipv6.conf.all.disable_ipv6=0',
                '--dns', '127.0.0.1',
                'quay.io/freeipa/freeipa-server:almalinux-10',
                'ipa-server-install', '-U',
                '-r', self.realm,
                '--setup-dns',
                '--auto-forwarders',
                '--no-ntp',
                '--skip-mem-check'
            ]
            subprocess.run(cmd, check=True)
            logger.info("FreeIPA Podman container deployed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Podman deployment failed: {e}")
            self._cleanup_failed_deployment(container_name)
            raise

    def deploy_kubernetes(self, namespace: str = "freeipa"):
        """Deploy FreeIPA using Kubernetes"""
        if not self._check_runtime('kubectl'):
            raise RuntimeError("kubectl not found")

        try:
            with open('freeipa-k8s.yaml', 'r') as f:
                k8s_config = yaml.safe_load(f)

            k8s_config['metadata']['namespace'] = namespace
            k8s_config['spec']['template']['spec']['containers'][0]['env'].append({
                'name': 'PASSWORD',
                'value': self.admin_password
            })
            k8s_config['spec']['template']['spec']['containers'][0]['args'] = [
                'ipa-server-install', '-U',
                '-r', self.realm,
                '--setup-dns',
                '--auto-forwarders',
                '--no-ntp',
                '--skip-mem-check'
            ]

            with open('freeipa-k8s-deploy.yaml', 'w') as f:
                yaml.dump(k8s_config, f)

            subprocess.run(['kubectl', 'create', 'namespace', namespace], check=True, capture_output=True)
            subprocess.run(['kubectl', 'apply', '-f', 'freeipa-k8s-deploy.yaml'], check=True)
            logger.info("FreeIPA Kubernetes deployment created successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Kubernetes deployment failed: {e}")
            raise

    def deploy_ansible(self, inventory_file: str = "inventory/hosts"):
        """Deploy FreeIPA using Ansible"""
        if not self._check_runtime('ansible-playbook'):
            raise RuntimeError("Ansible not found")

        try:
            with open('playbook_sensitive_data.yml', 'w') as f:
                yaml.dump({
                    'ipaadmin_password': self.admin_password,
                    'ipadm_password': self.dm_password,
                    'ipaserver_domain': self.domain,
                    'ipaserver_realm': self.realm
                }, f)

            cmd = [
                'ansible-playbook', '-v',
                '-i', inventory_file,
                '--vault-password-file', '.vault_pass.txt',
                'playbooks/install-cluster.yml'
            ]
            subprocess.run(cmd, check=True)
            logger.info("FreeIPA Ansible deployment completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ansible deployment failed: {e}")
            raise
        finally:
            if os.path.exists('playbook_sensitive_data.yml'):
                os.remove('playbook_sensitive_data.yml')

    def deploy_webui(self):
        """Deploy FreeIPA Web UI"""
        try:
            # Clone Web UI repository if not present
            if not os.path.exists('freeipa-webui'):
                subprocess.run(['git', 'clone', 'https://github.com/freeipa/freeipa-webui.git'], check=True)

            # Setup Vagrant for Web UI
            os.chdir('freeipa-webui')
            subprocess.run(['vagrant', 'up'], check=True)

            # Get VM IP and update hosts file
            ip_output = subprocess.run(['vagrant', 'ssh-config'], capture_output=True, text=True)
            ip = [line.split()[1] for line in ip_output.stdout.splitlines() if 'HostName' in line][0]
            with open('/etc/hosts', 'a') as f:
                f.write(f"{ip} server.ipa.{self.domain}\n")

            # Install dependencies and start dev server
            subprocess.run(['nvm', 'install'], check=True)
            subprocess.run(['nvm', 'use'], check=True)
            subprocess.run(['npm', 'install'], check=True)
            subprocess.run(['npm', 'run', 'dev'], check=True, shell=True)
            logger.info(f"FreeIPA Web UI deployed successfully at https://server.ipa.{self.domain}/ipa/modern-ui/")
        except subprocess.CalledProcessError as e:
            logger.error(f"Web UI deployment failed: {e}")
            raise
        finally:
            os.chdir('..')

    def deploy(self):
        """Main deployment method"""
        logger.info(f"Starting FreeIPA deployment with {self.deployment_type}")

        try:
            if self.deployment_type == "docker":
                self.deploy_docker()
            elif self.deployment_type == "podman":
                self.deploy_podman()
            elif self.deployment_type == "kubernetes":
                self.deploy_kubernetes()
            elif self.deployment_type == "ansible":
                self.deploy_ansible()
            else:
                raise ValueError(f"Unsupported deployment type: {self.deployment_type}")

            if self.config.get('deploy_webui', False):
                self.deploy_webui()
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='FreeIPA Automated Deployment')
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    parser.add_argument('--type', choices=['docker', 'podman', 'kubernetes', 'ansible'],
                       default='docker', help='Deployment type')

    args = parser.parse_args()

    deployer = FreeIPADeployer(args.config, args.type)
    deployer.deploy()

if __name__ == '__main__':
    main()