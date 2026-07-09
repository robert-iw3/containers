import subprocess
import argparse
import os
import yaml
import logging
from pathlib import Path
import secrets
import string

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_secret(length=32):
    """Generate a secure random secret for TinyAuth."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def check_requirements():
    """Check if required tools are installed."""
    tools = ['docker', 'podman', 'kubectl', 'ansible-playbook']
    missing_tools = []

    for tool in tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)

    if missing_tools:
        logger.error(f"Missing required tools: {', '.join(missing_tools)}")
        exit(1)

def create_env_file(env_path='.env'):
    """Create or update .env file with secure defaults."""
    env_vars = {
        'PORT': '3000',
        'ADDRESS': '0.0.0.0',
        'SECRET': generate_secret(),
        'APP_URL': 'https://tinyauth.example.com',
        'USERS': 'admin:$2a$10$UdLYoJ5lgPsC0RKqYH/jMua7zIn0g9kPqWmhYayJYLaZQ/FTmH2/u',
        'COOKIE_SECURE': 'true',
        'SESSION_EXPIRY': '7200',
        'LOGIN_TIMEOUT': '300',
        'LOGIN_MAX_RETRIES': '5',
        'LOG_LEVEL': '0',
        'APP_TITLE': 'TinyAuth SSO',
        'FORGOT_PASSWORD_MESSAGE': 'Contact admin to reset password',
        'OAUTH_AUTO_REDIRECT': 'none'
    }

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    logger.info(f"Created/updated {env_path}")

def deploy_docker_compose():
    """Deploy using Docker Compose."""
    try:
        subprocess.run(['docker-compose', '-f', 'compose.yml', 'up', '-d'], check=True)
        logger.info("Successfully deployed using Docker Compose")
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker Compose deployment failed: {e}")
        exit(1)

def deploy_podman_compose():
    """Deploy using Podman Compose."""
    try:
        subprocess.run(['podman-compose', '-f', 'compose.yml', 'up', '-d'], check=True)
        logger.info("Successfully deployed using Podman Compose")
    except subprocess.CalledProcessError as e:
        logger.error(f"Podman Compose deployment failed: {e}")
        exit(1)

def deploy_kubernetes():
    """Deploy to Kubernetes."""
    try:
        subprocess.run(['kubectl', 'apply', '-f', 'k8s/tinyauth-deployment.yml'], check=True)
        subprocess.run(['kubectl', 'apply', '-f', 'k8s/tinyauth-service.yml'], check=True)
        logger.info("Successfully deployed to Kubernetes")
    except subprocess.CalledProcessError as e:
        logger.error(f"Kubernetes deployment failed: {e}")
        exit(1)

def deploy_ansible():
    """Deploy using Ansible."""
    try:
        subprocess.run(['ansible-playbook', 'ansible/tinyauth-playbook.yml'], check=True)
        logger.info("Successfully deployed using Ansible")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ansible deployment failed: {e}")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description="Automated deployment for TinyAuth")
    parser.add_argument('--method', choices=['docker', 'podman', 'kubernetes', 'ansible'],
                       required=True, help="Deployment method")
    parser.add_argument('--env-file', default='.env', help="Path to .env file")
    args = parser.parse_args()

    # Check requirements
    check_requirements()

    # Create .env file if it doesn't exist
    if not os.path.exists(args.env_file):
        create_env_file(args.env_file)

    # Deploy based on chosen method
    if args.method == 'docker':
        deploy_docker_compose()
    elif args.method == 'podman':
        deploy_podman_compose()
    elif args.method == 'kubernetes':
        deploy_kubernetes()
    elif args.method == 'ansible':
        deploy_ansible()

if __name__ == "__main__":
    main()