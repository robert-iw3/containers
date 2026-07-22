#!/usr/bin/env python3
import subprocess
import os
import logging
import re
import boto3
from datetime import datetime

# Setting up logging
LOG_FILE = "/var/log/defguard.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Configuration variables (injected by Terraform templatefile)
CONFIG = {
    "proxy_url": "${proxy_url}",
    "grpc_port": "${grpc_port}",
    "arch": "${arch}",
    "package_version": "${package_version}",
    "http_port": "${http_port}",
    "log_level": "${log_level}",
    "secrets_manager_arn": "${secrets_manager_arn}"
}

def validate_input(value, name, pattern=None):
    """Validate input to prevent injection attacks."""
    if pattern and not re.match(pattern, str(value)):
        logger.error(f"Invalid {name}: {value}")
        raise ValueError(f"Invalid {name}: {value}")
    return value

def run_command(command, check=True):
    """Run a shell command and log output."""
    logger.info(f"Executing command: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=check, capture_output=True, text=True)
        logger.info(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e.stderr}")
        raise

def install_defguard_proxy():
    """Install the Defguard Proxy package."""
    logger.info("Updating apt repositories...")
    run_command(["apt", "update"])

    logger.info("Installing curl...")
    run_command(["apt", "install", "-y", "curl"])

    package_url = f"https://github.com/DefGuard/proxy/releases/download/v{validate_input(CONFIG['package_version'], 'package_version', r'^[0-9]+\.[0-9]+\.[0-9]+$')}/defguard-proxy-{CONFIG['package_version']}-{CONFIG['arch']}-unknown-linux-gnu.deb"
    package_path = "/tmp/defguard-proxy.deb"

    logger.info("Downloading defguard-proxy package...")
    run_command(["curl", "-fsSL", "-o", package_path, package_url])

    logger.info("Installing defguard-proxy package...")
    run_command(["dpkg", "-i", package_path])

def write_config():
    """Write the Defguard Proxy configuration file."""
    config_path = "/etc/defguard/proxy.toml"
    logger.info(f"Writing configuration to {config_path}...")

    config_content = f"""# Defguard Proxy configuration
http_port = {validate_input(CONFIG['http_port'], 'http_port', r'^\d+$')}
grpc_port = {validate_input(CONFIG['grpc_port'], 'grpc_port', r'^\d+$')}
log_level = "{validate_input(CONFIG['log_level'], 'log_level', r'^(trace|debug|info|warn|error)$')}"
rate_limit_per_second = 0
rate_limit_burst = 0
url = "{validate_input(CONFIG['proxy_url'], 'proxy_url', r'^https?://')}"
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    os.chmod(config_path, 0o600)  # Secure file permissions
    logger.info(f"Configuration written to {config_path} with secure permissions")

def configure_service():
    """Enable and start the Defguard Proxy service."""
    logger.info("Enabling defguard-proxy service...")
    run_command(["systemctl", "enable", "defguard-proxy"])

    logger.info("Starting defguard-proxy service...")
    run_command(["systemctl", "start", "defguard-proxy"])

def cleanup():
    """Clean up temporary files."""
    package_path = "/tmp/defguard-proxy.deb"
    if os.path.exists(package_path):
        logger.info("Cleaning up temporary files...")
        os.remove(package_path)
        logger.info("Cleanup completed.")

def main():
    """Main function to orchestrate the setup process."""
    try:
        install_defguard_proxy()
        write_config()
        configure_service()
        cleanup()
        logger.info("Setup completed successfully.")
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()