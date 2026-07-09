import argparse
import yaml
import subprocess
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path):
    """Load the YAML configuration file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        raise

def validate_config(config):
    """Validate the configuration file."""
    required_keys = [
        'deployment.target', 'deployment.ansible_inventory', 'deployment.ansible_playbook_dir',
        'redmine.version', 'redmine.port', 'redmine.http_port', 'redmine.secret_token', 'redmine.timezone',
        'postgres.user', 'postgres.password', 'postgres.db', 'postgres.port',
        'haproxy.http_port', 'haproxy.https_port',
        'paths.certs', 'paths.errors', 'paths.haproxy_config', 'paths.docker_socket'
    ]
    for key in required_keys:
        keys = key.split('.')
        current = config
        for k in keys:
            if k not in current:
                logger.error(f"Missing configuration key: {key}")
                raise ValueError(f"Missing configuration key: {key}")
            current = current[k]
    if config['deployment']['target'] not in ['docker', 'podman', 'kubernetes']:
        logger.error(f"Invalid deployment target: {config['deployment']['target']}")
        raise ValueError(f"Invalid deployment target: {config['deployment']['target']}")

def run_ansible_playbook(playbook_path, inventory_path, extra_vars):
    """Run an Ansible playbook with the given parameters."""
    cmd = [
        'ansible-playbook',
        '-i', inventory_path,
        playbook_path,
        '--extra-vars', f'"{extra_vars}"'
    ]
    logger.info(f"Running Ansible playbook: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Ansible playbook failed: {e.stderr}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Deploy Redmine using Ansible')
    parser.add_argument('--target', choices=['docker', 'podman', 'kubernetes'], default='docker',
                        help='Deployment target (docker, podman, kubernetes)')
    parser.add_argument('--config', default='config/deployment_config.yml',
                        help='Path to the configuration YAML file')
    args = parser.parse_args()

    # Load and validate configuration
    config = load_config(args.config)
    config['deployment']['target'] = args.target
    validate_config(config)

    # Prepare Ansible extra variables
    extra_vars = f"postgres_user={config['postgres']['user']} " \
                 f"postgres_password={config['postgres']['password']} " \
                 f"postgres_db={config['postgres']['db']} " \
                 f"postgres_port={config['postgres']['port']} " \
                 f"timezone={config['redmine']['timezone']} " \
                 f"redmine_port={config['redmine']['port']} " \
                 f"redmine_http_port={config['redmine']['http_port']} " \
                 f"redmine_secret_token={config['redmine']['secret_token']} " \
                 f"smtp_enabled={config['smtp']['enabled']} " \
                 f"smtp_domain={config['smtp']['domain']} " \
                 f"smtp_host={config['smtp']['host']} " \
                 f"smtp_port={config['smtp']['port']} " \
                 f"smtp_user={config['smtp']['user']} " \
                 f"smtp_password={config['smtp']['password']} " \
                 f"haproxy_http_port={config['haproxy']['http_port']} " \
                 f"haproxy_https_port={config['haproxy']['https_port']} " \
                 f"certs_path={config['paths']['certs']} " \
                 f"errors_path={config['paths']['errors']} " \
                 f"haproxy_config_path={config['paths']['haproxy_config']} " \
                 f"docker_socket={config['paths']['docker_socket']}"

    if config['deployment']['target'] == 'kubernetes':
        extra_vars += f" kubernetes_namespace={config['kubernetes']['namespace']} " \
                      f"kubernetes_replicas={config['kubernetes']['replicas']}"

    # Select playbook based on target
    playbook_map = {
        'docker': 'deploy_docker.yml',
        'podman': 'deploy_podman.yml',
        'kubernetes': 'deploy_kubernetes.yml'
    }
    playbook_path = os.path.join(config['deployment']['ansible_playbook_dir'], playbook_map[config['deployment']['target']])

    # Run Ansible playbook
    run_ansible_playbook(playbook_path, config['deployment']['ansible_inventory'], extra_vars)

if __name__ == '__main__':
    main()