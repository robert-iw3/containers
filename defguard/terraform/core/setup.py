#!/usr/bin/env python3
import subprocess
import os
import logging
import json
import secrets
import boto3
import re
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
    "db_address": "${db_address}",
    "db_name": "${db_name}",
    "db_username": "${db_username}",
    "db_port": "${db_port}",
    "core_url": "${core_url}",
    "proxy_address": "${proxy_address}",
    "proxy_grpc_port": "${proxy_grpc_port}",
    "proxy_url": "${proxy_url}",
    "grpc_port": "${grpc_port}",
    "http_port": "${http_port}",
    "package_version": "${package_version}",
    "arch": "${arch}",
    "cookie_insecure": "${cookie_insecure}",
    "log_level": "${log_level}",
    "secrets_manager_arn": "${secrets_manager_arn}",
    "vpn_networks": "${jsonencode(vpn_networks)}"
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

def generate_secret(length=64):
    """Generate a cryptographically secure secret."""
    return secrets.token_urlsafe(length)[:length]

def fetch_secrets(secrets_arn):
    """Fetch sensitive data from AWS Secrets Manager."""
    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secrets_arn)
        return json.loads(response["SecretString"])
    except Exception as e:
        logger.error(f"Failed to fetch secrets: {str(e)}")
        raise

def install_defguard():
    """Install the Defguard Core package."""
    logger.info("Updating apt repositories...")
    run_command(["apt", "update"])

    logger.info("Installing curl...")
    run_command(["apt", "install", "-y", "curl"])

    package_url = f"https://github.com/DefGuard/defguard/releases/download/v{validate_input(CONFIG['package_version'], 'package_version', r'^[0-9]+\.[0-9]+\.[0-9]+$')}/defguard-{CONFIG['package_version']}-{CONFIG['arch']}-unknown-linux-gnu.deb"
    package_path = "/tmp/defguard-core.deb"

    logger.info("Downloading defguard-core package...")
    run_command(["curl", "-fsSL", "-o", package_path, package_url])

    logger.info("Installing defguard-core package...")
    run_command(["dpkg", "-i", package_path])

def write_config(secrets):
    """Write the Defguard Core configuration file."""
    config_path = "/etc/defguard/core.conf"
    logger.info(f"Writing configuration to {config_path}...")

    config_content = f"""### Core configuration ###
DEFGUARD_AUTH_SECRET={generate_secret(64)}
DEFGUARD_GATEWAY_SECRET={secrets['gateway_secret']}
DEFGUARD_YUBIBRIDGE_SECRET={generate_secret(64)}
DEFGUARD_SECRET_KEY={generate_secret(64)}
DEFGUARD_URL={validate_input(CONFIG['core_url'], 'core_url', r'^https?://')}
DEFGUARD_AUTH_SESSION_LIFETIME=604800
DEFGUARD_ADMIN_GROUPNAME=admin
DEFGUARD_DEFAULT_ADMIN_PASSWORD={secrets['default_admin_password']}
DEFGUARD_GRPC_PORT={validate_input(CONFIG['grpc_port'], 'grpc_port', r'^\d+$')}
DEFGUARD_HTTP_PORT={validate_input(CONFIG['http_port'], 'http_port', r'^\d+$')}
DEFGUARD_COOKIE_INSECURE={str(CONFIG['cookie_insecure']).lower()}
DEFGUARD_LOG_LEVEL={validate_input(CONFIG['log_level'], 'log_level', r'^(trace|debug|info|warn|error)$')}

### Proxy configuration ###
DEFGUARD_PROXY_URL=http://{validate_input(CONFIG['proxy_address'], 'proxy_address', r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')}:{validate_input(CONFIG['proxy_grpc_port'], 'proxy_grpc_port', r'^\d+$')}
DEFGUARD_ENROLLMENT_URL={validate_input(CONFIG['proxy_url'], 'proxy_url', r'^https?://')}

### DB configuration ###
DEFGUARD_DB_HOST={validate_input(CONFIG['db_address'], 'db_address')}
DEFGUARD_DB_PORT={validate_input(CONFIG['db_port'], 'db_port', r'^\d+$')}
DEFGUARD_DB_NAME={validate_input(CONFIG['db_name'], 'db_name', r'^[a-zA-Z0-9_]+$')}
DEFGUARD_DB_USER={validate_input(CONFIG['db_username'], 'db_username', r'^[a-zA-Z0-9_]+$')}
DEFGUARD_DB_PASSWORD={secrets['db_password']}
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    os.chmod(config_path, 0o600)  # Secure file permissions
    logger.info(f"Configuration written to {config_path} with secure permissions")

def setup_service():
    """Enable and start the Defguard service."""
    logger.info("Enabling defguard service...")
    run_command(["systemctl", "enable", "defguard"])

    logger.info("Starting defguard service...")
    run_command(["systemctl", "start", "defguard"])

def configure_vpn_networks(secrets):
    """Configure VPN locations."""
    for network in json.loads(CONFIG["vpn_networks"]):
        logger.info(f"Creating VPN location {network['name']}...")
        cmd = [
            "/usr/bin/defguard",
            "--secret-key", secrets["gateway_secret"],
            "init-vpn-location",
            "--name", validate_input(network["name"], "network_name", r'^[a-zA-Z0-9_]+$'),
            "--address", validate_input(network["address"], "network_address", r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$'),
            "--endpoint", validate_input(network["endpoint"], "network_endpoint"),
            "--port", str(validate_input(network["port"], "network_port", r'^\d+$')),
            "--id", str(network["id"]),
            "--allowed-ips", validate_input(network["address"], "allowed_ips", r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$')
        ]
        run_command(cmd)
        logger.info(f"Created VPN location {network['name']}")

def cleanup():
    """Clean up temporary files."""
    package_path = "/tmp/defguard-core.deb"
    if os.path.exists(package_path):
        logger.info("Cleaning up temporary files...")
        os.remove(package_path)
        logger.info("Cleanup completed.")

def main():
    """Main function to orchestrate the setup process."""
    try:
        secrets = fetch_secrets(CONFIG["secrets_manager_arn"])
        install_defguard()
        write_config(secrets)
        setup_service()
        configure_vpn_networks(secrets)
        cleanup()
        logger.info("Setup completed successfully.")
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()