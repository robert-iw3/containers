# deploy.py
import os
import subprocess
import random
import string
import base64
import yaml
import sys
import argparse

def load_config():
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    if not config['tinyauth']['secret']:
        config['tinyauth']['secret'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
    if not config['tinyauth']['password']:
        config['tinyauth']['password'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
    config['tinyauth']['users'] = subprocess.check_output(['htpasswd', '-Bbn', 'tinyauth', config['tinyauth']['password']]).decode().strip().replace('$', '$$')
    return config

def generate_env_temp(config):
    with open('.env.temp', 'w') as f:
        for key, value in config['authority'].items():
            f.write(f"{key.upper()}={value}\n")

def generate_certs():
    subprocess.check_call(['docker', 'build', '-t', 'certs:latest', 'certs'])
    subprocess.check_call(['docker', 'run', '--rm', '-v', './secrets/certs:/certs', '--env-file', '.env.temp', 'certs:latest'])

def update_files(config):
    # Update docker-compose.yaml with secret and users
    with open('docker-compose.yaml', 'r') as f:
        content = f.read()
    content = content.replace('SECRET= # Replace', f"SECRET={config['tinyauth']['secret']}")
    content = content.replace('USERS= # Replace', f"USERS={config['tinyauth']['users']}")
    with open('docker-compose.yaml', 'w') as f:
        f.write(content)

    # Update tinyauth-k8s.yaml with base64
    secret_b64 = base64.b64encode(config['tinyauth']['secret'].encode()).decode()
    users_b64 = base64.b64encode(config['tinyauth']['users'].encode()).decode()
    with open('tinyauth-k8s.yaml', 'r') as f:
        content = f.read()
    content = content.replace('secret: eW91cl9iYXNlNjRfZ2VuZXJhdGVkX3NlY3JldA==', f"secret: {secret_b64}")
    content = content.replace('users: dGlueWF1dGg6JDJ5JDEwJHlvdXJfaGFzaA==', f"users: {users_b64}")
    with open('tinyauth-k8s.yaml', 'w') as f:
        f.write(content)

    # Update falco-values.yaml if slack webhook
    with open('falco-values.yaml', 'r') as f:
        content = f.read()
    content = content.replace('webhookurl: ""', f"webhookurl: \"{config['falcosidekick']['slack_webhook']}\"")
    with open('falco-values.yaml', 'w') as f:
        f.write(content)

if __name__ == '__main__':
    config = load_config()
    generate_env_temp(config)
    generate_certs()
    update_files(config)
    print("Files finalized. Run deployments as per README.md")
    os.remove('.env.temp')