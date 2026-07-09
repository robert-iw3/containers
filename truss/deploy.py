import subprocess
import yaml
import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def check_python_dependencies():
    """Check if required Python packages are installed."""
    try:
        import yaml
        logger.info("PyYAML is installed")
    except ImportError:
        logger.error("PyYAML is not installed. Install it with: pip install pyyaml")
        sys.exit(1)

def load_config(config_path="vars/config.yml"):
    """Load configuration from vars/config.yml."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        required = ["model_name", "model_requirements", "python_version", "python_image_hash"]
        missing = [key for key in required if key not in config or not config[key]]
        if missing:
            logger.error(f"Missing required config keys: {', '.join(missing)}")
            sys.exit(1)
        return config
    except FileNotFoundError:
        logger.error(f"Config file {config_path} not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing {config_path}: {e}")
        sys.exit(1)

def check_prerequisites(config):
    """Check if required tools are installed."""
    try:
        subprocess.run(["ansible", "--version"], check=True, capture_output=True)
        logger.info("Ansible is installed")
    except subprocess.CalledProcessError:
        logger.error("Ansible is not installed")
        sys.exit(1)

    if not config.get("use_kubernetes", False):
        try:
            binary = "podman" if config.get("use_podman", False) else "docker"
            subprocess.run([binary, "--version"], check=True, capture_output=True)
            logger.info(f"{binary.capitalize()} is installed")
        except subprocess.CalledProcessError:
            logger.error(f"{binary.capitalize()} is not installed")
            sys.exit(1)
    else:
        try:
            subprocess.run(["kubectl", "get", "nodes"], check=True, capture_output=True)
            logger.info("kubectl is installed and cluster is accessible")
        except subprocess.CalledProcessError:
            logger.error("kubectl is not installed or cluster is not accessible")
            sys.exit(1)

def run_ansible_playbook(inventory="inventory"):
    """Run the Ansible playbook."""
    playbook = "ansible-deployment.yml"
    if not Path(playbook).exists():
        logger.error(f"Playbook {playbook} not found")
        sys.exit(1)

    if not Path(inventory).exists():
        logger.error(f"Inventory file {inventory} not found")
        sys.exit(1)

    cmd = ["ansible-playbook", playbook, "-i", inventory]
    logger.info(f"Running: {' '.join(cmd)}")
    for attempt in range(3):
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("Deployment successful")
            logger.debug(result.stdout)
            return
        except subprocess.CalledProcessError as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e.stderr}")
            if attempt == 2:
                logger.error("Deployment failed after 3 attempts")
                sys.exit(1)

def main():
    """Main function to initiate deployment."""
    check_python_dependencies()
    config = load_config()
    check_prerequisites(config)
    inventory = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    run_ansible_playbook(inventory)

if __name__ == "__main__":
    main()