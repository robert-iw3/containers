import os
import yaml
import subprocess
import logging
import argparse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import shutil
import hvac

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_tools(platform):
    """Validate required tools are installed for the specified platform."""
    tools = ['ansible-playbook']
    if platform in ['docker', 'podman']:
        tools.append('docker-compose' if platform == 'docker' else 'podman-compose')
    elif platform == 'kubernetes':
        tools.extend(['kubectl', 'helm'])
    for tool in tools:
        if not shutil.which(tool):
            logger.error(f"Required tool {tool} not found")
            raise RuntimeError(f"{tool} is not installed")

def load_vault_secrets(vault_config):
    """Fetch secrets from HashiCorp Vault using provided configuration."""
    try:
        token = os.environ.get('VAULT_TOKEN')
        if not token:
            raise ValueError("VAULT_TOKEN environment variable not set")
        client = hvac.Client(url=vault_config['url'], token=token)
        secret_path = vault_config['secret_path']
        response = client.secrets.kv.v2.read_secret_version(path=secret_path)
        return response['data']['data']
    except Exception as e:
        logger.error(f"Failed to fetch Vault secrets: {e}")
        raise

def load_config(config_path):
    """Load and validate configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        required = ['rudder_version', 'image_registry', 'namespace', 'replicas', 'vault']
        for field in required:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        if config['replicas'] < 1:
            raise ValueError("replicas must be positive")
        config['secrets'] = load_vault_secrets(config['vault'])
        logger.info(f"Loaded configuration: {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise

def render_template(template_path, output_path, context):
    """Render Jinja2 template with provided context to output path."""
    env = Environment(loader=FileSystemLoader('templates'))
    try:
        template = env.get_template(template_path)
        rendered = template.render(**context)
        with open(output_path, 'w') as f:
            f.write(rendered)
        logger.info(f"Rendered template {template_path} to {output_path}")
    except Exception as e:
        logger.error(f"Template rendering failed: {e}")
        raise

def run_ansible_playbook(playbook_path, inventory_path, extra_vars):
    """Execute Ansible playbook with specified inventory and extra variables."""
    cmd = f"ansible-playbook -i {inventory_path} {playbook_path} --extra-vars '{extra_vars}'"
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"Ansible playbook {playbook_path} executed successfully")
        logger.debug(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Ansible playbook failed: {e.stderr}")
        raise

def main():
    """Main function to orchestrate RudderStack deployment."""
    parser = argparse.ArgumentParser(description="RudderStack Deployment Script")
    parser.add_argument('--config', default='config/config.yaml', help='Path to configuration YAML file')
    parser.add_argument('--platform', choices=['docker', 'podman', 'kubernetes'], required=True, help='Deployment platform')
    args = parser.parse_args()

    check_tools(args.platform)
    config = load_config(args.config)
    base_dir = Path(__file__).parent
    templates_dir = base_dir / 'templates'
    output_dir = base_dir / 'generated'
    output_dir.mkdir(exist_ok=True)

    context = {
        'rudder_version': config.get('rudder_version', '1.80.0'),
        'transformer_version': config.get('transformer_version', '1.41.1'),
        'image_registry': config.get('image_registry', 'docker.io'),
        'namespace': config.get('namespace', 'rudderstack'),
        'replicas': config.get('replicas', 1),
        'workspace_token': config['secrets'].get('workspace_token', ''),
        'postgres_password': config['secrets'].get('postgres_password', ''),
        'enable_logging': config.get('enable_logging', False),
        'config_backend_url': config.get('config_backend_url', 'https://api.rudderstack.com'),
        'enable_telemetry': config.get('enable_telemetry', True),
    }

    if args.platform == 'docker':
        render_template('docker-compose.j2', output_dir / 'docker-compose.yml', context)
        playbook = 'playbooks/deploy_docker.yml'
    elif args.platform == 'podman':
        render_template('docker-compose.j2', output_dir / 'docker-compose.yml', context)
        playbook = 'playbooks/deploy_podman.yml'
    else:  # kubernetes
        render_template('k8s-helm-values.j2', output_dir / 'values.yml', context)
        render_template('k8s-network-policy.j2', output_dir / 'network-policy.yml', context)
        playbook = 'playbooks/deploy_kubernetes.yml'

    extra_vars = f"platform={args.platform}"
    run_ansible_playbook(base_dir / playbook, base_dir / 'inventory/hosts.ini', extra_vars)

if __name__ == '__main__':
    main()