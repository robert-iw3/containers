import os
import subprocess
import argparse
import yaml
import sys
import logging
from pathlib import Path
from tqdm import tqdm

# Configure logging
logging.basicConfig(filename='logs/deployment.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run_command(command, error_message):
    """Execute a shell command and handle errors."""
    logging.info(f"Executing command: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"Command output: {result.stdout}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"{error_message}: {e.stderr}")
        print(f"Error: {error_message}. Check logs/deployment.log for details.")
        sys.exit(1)

def load_config(config_file):
    """Load and validate deployment configuration."""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        required_keys = ['splunk_version', 'splunk_uf_version', 'splunk_home', 'splunk_uf_home',
                        'splunk_instance_size', 'indexing_volume', 'allowed_cidr']
        for key in required_keys:
            if key not in config:
                logging.error(f"Missing required config key: {key}")
                print(f"Error: Missing required configuration key: {key}")
                sys.exit(1)
        if config['splunk_instance_size'] not in ['small', 'medium', 'large']:
            logging.error(f"Invalid splunk_instance_size: {config['splunk_instance_size']}")
            print("Error: splunk_instance_size must be 'small', 'medium', or 'large'")
            sys.exit(1)
        if not isinstance(config['indexing_volume'], int) or config['indexing_volume'] <= 0:
            logging.error(f"Invalid indexing_volume: {config['indexing_volume']}")
            print("Error: indexing_volume must be a positive integer")
            sys.exit(1)
        return config
    except Exception as e:
        logging.error(f"Error loading config file {config_file}: {e}")
        print(f"Error loading config file {config_file}. Check logs/deployment.log.")
        sys.exit(1)

def update_inventory(config, server_ip, uf_ip, inventory_file):
    """Update Ansible inventory with provided IPs or localhost."""
    inventory_data = {
        'all': {
            'hosts': {
                'splunk_server': {'ansible_host': server_ip},
                'splunk_uf': {'ansible_host': uf_ip}
            },
            'vars': config
        }
    }
    with open(inventory_file, 'w') as f:
        yaml.dump(inventory_data, f, default_flow_style=False)
    logging.info(f"Updated inventory file: {inventory_file}")
    print(f"Updated inventory file: {inventory_file}")

def deploy_aws(config):
    """Handle AWS deployment using Terraform."""
    print("Initializing Terraform...")
    run_command(['terraform', 'init'], "Failed to initialize Terraform")

    print("Applying Terraform configuration...")
    instance_size = 't3.' + config.get('splunk_instance_size', 'medium')
    for _ in tqdm(range(1), desc="Applying Terraform"):
        run_command(['terraform', 'apply', '-auto-approve',
                     '-var', 'deployment_type=aws',
                     '-var', f'instance_type={instance_size}',
                     '-var', f'indexing_volume={config.get("indexing_volume", 100)}',
                     '-var', f'allowed_cidr={config.get("allowed_cidr", "0.0.0.0/0")}'],
                    "Failed to apply Terraform configuration")

    server_ip = run_command(['terraform', 'output', '-raw', 'splunk_server_public_ip'],
                           "Failed to get Splunk server IP")
    uf_ip = server_ip  # UF on same host
    update_inventory(config, server_ip.strip(), uf_ip.strip(), 'ansible/inventory.yml')

    print("Running Ansible playbook...")
    for _ in tqdm(range(1), desc="Running Ansible"):
        run_command(['ansible-playbook', '-i', 'ansible/inventory.yml',
                     'ansible/splunk_deployment.yml'], "Failed to run Ansible playbook")

def deploy_bare_metal(config):
    """Handle bare metal deployment."""
    update_inventory(config, 'localhost', 'localhost', 'ansible/inventory.yml')

    print("Running Ansible playbook for bare metal...")
    for _ in tqdm(range(1), desc="Running Ansible"):
        run_command(['ansible-playbook', '-i', 'ansible/inventory.yml',
                     'ansible/splunk_deployment.yml'], "Failed to run Ansible playbook")

def main():
    parser = argparse.ArgumentParser(description="Deploy Splunk Enterprise with Universal Forwarder")
    parser.add_argument('--type', choices=['aws', 'bare_metal'], default='bare_metal',
                       help="Deployment type: aws or bare_metal")
    parser.add_argument('--config', default='config/deployment_config.yaml',
                       help="Path to deployment configuration file")
    args = parser.parse_args()

    logging.info(f"Starting Splunk deployment (type: {args.type}, config: {args.config})")
    required_files = [
        'ansible/splunk_deployment.yml',
        'ansible/roles/splunk_enterprise/templates/server.conf.j2',
        'ansible/roles/splunk_enterprise/templates/web.conf.j2',
        'ansible/roles/splunk_enterprise/templates/inputs.conf.j2',
        'ansible/roles/splunk_forwarder/templates/outputs.conf.j2',
        'ansible/roles/splunk_enterprise/templates/props.conf.j2',
        'ansible/roles/splunk_enterprise/templates/tags.conf.j2',
        'ansible/roles/splunk_enterprise/templates/monitoring.conf.j2',
        'ansible/roles/splunk_enterprise/templates/limits.conf.j2',
        'ansible/roles/splunk_enterprise/templates/indexes.conf.j2',
        'ansible/roles/splunk_enterprise/templates/thruput.conf.j2',
        'ansible/ansible.cfg'
    ]
    for file in required_files:
        if not Path(file).exists():
            logging.error(f"Required file {file} not found")
            print(f"Error: Required file {file} not found")
            sys.exit(1)

    config = load_config(args.config)
    print(f"Starting Splunk deployment ({args.type})...")

    try:
        if args.type == 'aws':
            deploy_aws(config)
        else:
            deploy_bare_metal(config)

        print("Running health check...")
        run_command(['python', 'scripts/check_health.py', args.type], "Health check failed")
        logging.info("Splunk deployment completed successfully")
        print("Splunk deployment completed successfully!")
    except Exception as e:
        logging.error(f"Deployment failed: {str(e)}")
        print("Deployment failed. Running cleanup...")
        run_command(['python', 'scripts/cleanup_deployment.py', args.type], "Cleanup failed")
        sys.exit(1)

if __name__ == '__main__':
    main()