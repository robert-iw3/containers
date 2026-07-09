import os
import subprocess
import logging
import getpass
import re
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def check_command(command):
    """Check if a command is available on the system."""
    try:
        subprocess.run([command, '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def get_user_input(prompt, secure=False, validation_func=None):
    """Get user input, optionally secure (hidden) or validated."""
    while True:
        value = getpass.getpass(prompt) if secure else input(prompt)
        if not value:
            logger.error("Input cannot be empty.")
            continue
        if validation_func and not validation_func(value):
            logger.error("Invalid input format.")
            continue
        return value

def setup_environment():
    """Prompt for and set environment variables."""
    logger.info("Setting up environment variables for Burp Suite deployment...")
    env_vars = {
        'PORTSWIGGER_EMAIL_ADDRESS': get_user_input(
            "Enter PortSwigger email address: ",
            validation_func=validate_email
        ),
        'PORTSWIGGER_PASSWORD': get_user_input(
            "Enter PortSwigger password: ",
            secure=True
        ),
        'BURP_SUITE_PRO_VERSION': get_user_input(
            "Enter Burp Suite Pro version (e.g., 2025.8.2): "
        ),
        'BURP_SUITE_PRO_CHECKSUM': get_user_input(
            "Enter Burp Suite Pro SHA256 checksum: "
        ),
        'BURP_KEY': get_user_input(
            "Enter Burp Suite license key: ",
            secure=True
        )
    }
    for key, value in env_vars.items():
        os.environ[key] = value
    return env_vars

def check_files():
    """Verify required files exist."""
    required_files = [
        'Dockerfile',
        'docker-compose.yml',
        'burp-deployment.yaml',
        'download.sh',
        'entrypoint.sh',
        'config/project_options.json'
    ]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        logger.error(f"Missing required files: {', '.join(missing_files)}")
        raise FileNotFoundError("Required files are missing.")

def deploy_docker():
    """Deploy Burp Suite using Docker Compose."""
    logger.info("Deploying Burp Suite with Docker Compose...")
    if not check_command('docker'):
        logger.error("Docker is not installed or not accessible.")
        raise RuntimeError("Docker is required for this deployment.")

    try:
        subprocess.run(['docker-compose', 'up', '-d'], check=True)
        logger.info("Burp Suite deployed successfully. Access at http://127.0.0.1:8080")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to deploy with Docker Compose: {e}")
        raise

def deploy_podman():
    """Deploy Burp Suite using Podman Compose."""
    logger.info("Deploying Burp Suite with Podman Compose...")
    if not check_command('podman'):
        logger.error("Podman is not installed or not accessible.")
        raise RuntimeError("Podman is required for this deployment.")
    if not check_command('podman-compose'):
        logger.error("Podman Compose is not installed. Install with 'pipx install podman-compose'.")
        raise RuntimeError("Podman Compose is required for this deployment.")

    try:
        subprocess.run(['podman-compose', 'up', '-d'], check=True)
        logger.info("Burp Suite deployed successfully. Access at http://127.0.0.1:8080")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to deploy with Podman Compose: {e}")
        raise

def deploy_kubernetes():
    """Deploy Burp Suite using Kubernetes."""
    logger.info("Deploying Burp Suite with Kubernetes...")
    if not check_command('kubectl'):
        logger.error("kubectl is not installed or not accessible.")
        raise RuntimeError("kubectl is required for this deployment.")

    registry = get_user_input("Enter container registry (e.g., docker.io/username): ")
    image_tag = f"{registry}/burp-suite-pro:latest"

    # Build and push Docker image
    try:
        logger.info("Building Docker image...")
        env_vars = {k: os.environ[k] for k in [
            'PORTSWIGGER_EMAIL_ADDRESS',
            'PORTSWIGGER_PASSWORD',
            'BURP_SUITE_PRO_VERSION',
            'BURP_SUITE_PRO_CHECKSUM'
        ]}
        build_args = [f"--build-arg {k}={v}" for k, v in env_vars.items()]
        subprocess.run(
            ['docker', 'build', '-t', image_tag] + build_args + ['.'],
            check=True
        )
        logger.info("Pushing Docker image to registry...")
        subprocess.run(['docker', 'push', image_tag], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to build or push Docker image: {e}")
        raise

    # Update image in Kubernetes manifest
    try:
        with open('burp-deployment.yaml', 'r') as f:
            manifest = f.read()
        manifest = manifest.replace('burp-suite-pro:latest', image_tag)
        with open('burp-deployment.yaml', 'w') as f:
            f.write(manifest)
    except IOError as e:
        logger.error(f"Failed to update Kubernetes manifest: {e}")
        raise

    # Create Kubernetes secret
    try:
        subprocess.run([
            'kubectl', 'create', 'secret', 'generic', 'burp-secrets',
            f"--from-literal=burp-key={os.environ['BURP_KEY']}",
            '-n', 'burp-suite'
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create Kubernetes secret: {e}")
        raise

    # Apply Kubernetes manifest
    try:
        subprocess.run(['kubectl', 'apply', '-f', 'burp-deployment.yaml'], check=True)
        logger.info("Burp Suite deployed successfully. Run the following to access:")
        logger.info("kubectl port-forward svc/burp-suite 8080:8080 -n burp-suite")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to deploy with Kubernetes: {e}")
        raise

def main():
    """Main function to handle deployment."""
    try:
        check_files()
        logger.info("Required files found.")

        print("Select deployment type:")
        print("1. Docker Compose")
        print("2. Podman Compose")
        print("3. Kubernetes")
        choice = get_user_input("Enter choice (1-3): ", validation_func=lambda x: x in ['1', '2', '3'])

        setup_environment()

        if choice == '1':
            deploy_docker()
        elif choice == '2':
            deploy_podman()
        else:
            deploy_kubernetes()

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()