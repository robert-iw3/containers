import os
import subprocess
import sys
import logging
from pathlib import Path
import argparse
import secrets
import string

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_secret(length=16):
    """Generate a random secret string."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def setup_secrets(secrets_dir: Path):
    """Create secrets files if they don't exist."""
    secrets_dir.mkdir(exist_ok=True)
    secrets_files = {
        'postgres_db.txt': 'artifactory',
        'postgres_user.txt': 'artifactory',
        'postgres_password.txt': generate_secret(),
    }
    for filename, default_value in secrets_files.items():
        file_path = secrets_dir / filename
        if not file_path.exists():
            with open(file_path, 'w') as f:
                f.write(default_value)
            logger.info(f"Created secret file: {filename}")

def check_requirements():
    """Check if required tools are installed."""
    tools = ['docker', 'podman', 'kubectl']
    available = []
    for tool in tools:
        try:
            subprocess.run([tool, '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            available.append(tool)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return available

def deploy_docker_compose():
    """Deploy using Docker Compose."""
    try:
        subprocess.run(['docker-compose', '-f', 'docker-compose.yml', 'up', '-d'], check=True)
        logger.info("Docker Compose deployment successful")
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker Compose deployment failed: {e}")
        sys.exit(1)

def deploy_podman():
    """Deploy using Podman."""
    try:
        subprocess.run(['podman-compose', '-f', 'docker-compose.yml', 'up', '-d'], check=True)
        logger.info("Podman deployment successful")
    except subprocess.CalledProcessError as e:
        logger.error(f"Podman deployment failed: {e}")
        sys.exit(1)

def deploy_kubernetes():
    """Deploy using Kubernetes."""
    try:
        subprocess.run(['kubectl', 'apply', '-f', 'artifactory-k8s.yml'], check=True)
        logger.info("Kubernetes deployment successful")
    except subprocess.CalledProcessError as e:
        logger.error(f"Kubernetes deployment failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Deploy Artifactory with Docker, Podman, or Kubernetes")
    parser.add_argument('--platform', choices=['docker', 'podman', 'kubernetes'], required=True,
                        help="Deployment platform")
    args = parser.parse_args()

    # Set up secrets
    secrets_dir = Path('secrets')
    setup_secrets(secrets_dir)

    # Check environment variables
    required_env = ['DOCKER_REGISTRY', 'ARTIFACTORY_VERSION', 'ROOT_DATA_DIR', 'JF_ROUTER_ENTRYPOINTS_EXTERNALPORT']
    missing = [var for var in required_env if not os.getenv(var)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Check available tools
    available_tools = check_requirements()
    if args.platform not in available_tools:
        logger.error(f"{args.platform} not installed or not working")
        sys.exit(1)

    # Deploy based on platform
    logger.info(f"Deploying Artifactory on {args.platform}")
    if args.platform == 'docker':
        deploy_docker_compose()
    elif args.platform == 'podman':
        deploy_podman()
    elif args.platform == 'kubernetes':
        deploy_kubernetes()

if __name__ == "__main__":
    main()