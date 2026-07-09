import yaml
import subprocess
import secrets
import string
import argparse
import os

def generate_password(length=32):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_config(config):
    if config['cert_type'] == 'letsencrypt' and not config['email']:
        raise ValueError("Email required for letsencrypt")
    if not config['domain']:
        raise ValueError("Domain must be set")
    if config['deployment_type'] not in ['docker', 'podman', 'kubernetes']:
        raise ValueError("Invalid deployment_type")
    if config['use_all_in_one'] and config['deployment_type'] == 'kubernetes':
        raise ValueError("All-in-one mode not supported in Kubernetes")

def main():
    parser = argparse.ArgumentParser(description="Deploy HyperDX via Ansible")
    parser.add_argument('--config', default='config.yaml', help='Path to config.yaml')
    parser.add_argument('--type', help='Override deployment_type in config')
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    if args.type:
        config['deployment_type'] = args.type

    validate_config(config)

    # Generate secrets if empty
    for key in ['clickhouse_agg_password', 'clickhouse_wrk_password', 'clickhouse_api_password', 'mongo_password']:
        if not config.get(key):
            config[key] = generate_password()
    if not config.get('api_key'):
        config['api_key'] = generate_password(64)

    # Write to ansible_vars.yaml
    vars_file = 'ansible_vars.yaml'
    with open(vars_file, 'w') as f:
        yaml.dump(config, f)

    # Run Ansible
    playbook = f"deploy_{config['deployment_type']}.yml"
    cmd = ['ansible-playbook', '-e', f'@{vars_file}', '-i', 'inventory.yml', playbook]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()