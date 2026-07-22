#!/usr/bin/env python3
import subprocess
import os
import logging
import json
import boto3
import re
import jwt
from datetime import datetime, timedelta

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
    "gateway_port": "${gateway_port}",
    "network_id": "${network_id}",
    "core_address": "${core_address}",
    "core_grpc_port": "${core_grpc_port}",
    "package_version": "${package_version}",
    "nat": "${nat}",
    "gateway_name": "${gateway_name}",
    "arch": "${arch}",
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

def fetch_secrets(secrets_arn):
    """Fetch sensitive data from AWS Secrets Manager."""
    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secrets_arn)
        return json.loads(response["SecretString"])
    except Exception as e:
        logger.error(f"Failed to fetch secrets: {str(e)}")
        raise

def install_defguard_gateway():
    """Install the Defguard Gateway package."""
    logger.info("Updating apt repositories...")
    run_command(["apt", "update"])

    logger.info("Installing curl...")
    run_command(["apt", "install", "-y", "curl"])

    package_url = f"https://github.com/DefGuard/gateway/releases/download/v{validate_input(CONFIG['package_version'], 'package_version', r'^[0-9]+\.[0-9]+\.[0-9]+$')}/defguard-gateway_{CONFIG['package_version']}_{CONFIG['arch']}-unknown-linux-gnu.deb"
    package_path = "/tmp/defguard-gateway.deb"

    logger.info("Downloading defguard-gateway package...")
    run_command(["curl", "-fsSL", "-o", package_path, package_url])

    logger.info("Installing defguard-gateway package...")
    run_command(["dpkg", "-i", package_path])

def generate_gateway_token(secrets):
    """Generate a JWT token for the gateway."""
    logger.info("Generating gateway token...")
    now = datetime.utcnow()
    expiration = now + timedelta(days=365 * 10)  # 10 years
    payload = {
        "iss": "DefGuard",
        "sub": f"DEFGUARD-NETWORK-{CONFIG['network_id']}",
        "client_id": str(CONFIG["network_id"]),
        "exp": int(expiration.timestamp()),
        "nbf": int(now.timestamp())
    }
    token = jwt.encode(payload, secrets["gateway_secret"], algorithm="HS256")
    return token

def write_config(secrets):
    """Write the Defguard Gateway configuration file."""
    config_path = "/etc/defguard/gateway.toml"
    logger.info(f"Writing configuration to {config_path}...")

    config_content = f"""# Defguard Gateway configuration
token = "{generate_gateway_token(secrets)}"
grpc_url = "http://{validate_input(CONFIG['core_address'], 'core_address', r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')}:{validate_input(CONFIG['core_grpc_port'], 'core_grpc_port', r'^\d+$')}"
name = "{validate_input(CONFIG['gateway_name'], 'gateway_name', r'^[a-zA-Z0-9_-]+$')}"
userspace = false
stats_period = 60
ifname = "wg0"
use_syslog = false
syslog_facility = "LOG_USER"
syslog_socket = "/var/run/log"
masquerade = {str(CONFIG['nat']).lower()}
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    os.chmod(config_path, 0o600)  # Secure file permissions
    logger.info(f"Configuration written to {config_path} with secure permissions")

def configure_nat():
    """Configure IP forwarding for NAT if enabled."""
    if CONFIG["nat"]:
        logger.info("Enabling IP forwarding for NAT (IPv4)...")
        run_command(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        with open("/etc/sysctl.conf", "a") as f:
            if "net.ipv4.ip_forward" not in open("/etc/sysctl.conf").read():
                f.write("net.ipv4.ip_forward = 1\n")

        logger.info("Enabling IP forwarding for NAT (IPv6)...")
        run_command(["sysctl", "-w", "net.ipv6.conf.all.forwarding=1"])
        with open("/etc/sysctl.conf", "a") as f:
            if "net.ipv6.conf.all.forwarding" not in open("/etc/sysctl.conf").read():
                f.write("net.ipv6.conf.all.forwarding = 1\n")

def configure_service():
    """Configure, enable, and start the Defguard Gateway service."""
    service_file = "/lib/systemd/system/defguard-gateway.service"
    logger.info(f"Setting log level in {service_file}...")

    log_level = validate_input(CONFIG["log_level"], "log_level", r"^(trace|debug|info|warn|error)$")
    with open(service_file, "r") as f:
        content = f.readlines()

    new_content = []
    replaced = False
    for line in content:
        if line.startswith('Environment="RUST_LOG='):
            new_content.append(f'Environment="RUST_LOG={log_level}"\n')
            replaced = True
        else:
            new_content.append(line)

    if not replaced:
        for i, line in enumerate(new_content):
            if line.strip() == "[Service]":
                new_content.insert(i + 1, f'Environment="RUST_LOG={log_level}"\n')
                break

    with open(service_file, "w") as f:
        f.writelines(new_content)

    logger.info("Reloading systemd daemon to apply changes...")
    run_command(["systemctl", "daemon-reload"])

    logger.info("Enabling defguard-gateway service...")
    run_command(["systemctl", "enable", "defguard-gateway"])

    logger.info("Starting defguard-gateway service...")
    run_command(["systemctl", "start", "defguard-gateway"])

def cleanup():
    """Clean up temporary files."""
    package_path = "/tmp/defguard-gateway.deb"
    if os.path.exists(package_path):
        logger.info("Cleaning up temporary files...")
        os.remove(package_path)
        logger.info("Cleanup completed.")

def main():
    """Main function to orchestrate the setup process."""
    try:
        secrets = fetch_secrets(CONFIG["secrets_manager_arn"])
        install_defguard_gateway()
        write_config(secrets)
        configure_nat()
        configure_service()
        cleanup()
        logger.info("Setup completed successfully.")
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()