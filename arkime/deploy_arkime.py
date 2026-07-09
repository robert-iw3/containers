#!/usr/bin/env python3

import os
import subprocess
import logging
import yaml
import argparse
import sys
from pathlib import Path
from typing import Dict, Optional
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('deploy_arkime.log')
    ]
)
logger = logging.getLogger(__name__)

class ArkimeDeployer:
    def __init__(self, compose_file: str = "docker-compose.yml", env_file: str = ".env"):
        self.compose_file = Path(compose_file)
        self.env_file = Path(env_file)
        self.env_vars = self.load_env_file()
        self.compose_data = self.load_compose_file()
        self.podman_compose_cmd = ["podman-compose", "-f", str(self.compose_file)]
        self.podman_cmd = ["podman"]

    def load_env_file(self) -> Dict[str, str]:
        """Load and parse the .env file."""
        env_vars = {}
        if not self.env_file.exists():
            logger.error(f"Environment file {self.env_file} not found")
            sys.exit(1)
        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
            logger.info(f"Loaded environment variables from {self.env_file}")
            return env_vars
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")
            sys.exit(1)

    def load_compose_file(self) -> Dict:
        """Load and parse the docker-compose.yml file."""
        if not self.compose_file.exists():
            logger.error(f"Compose file {self.compose_file} not found")
            sys.exit(1)
        try:
            with open(self.compose_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load compose file: {e}")
            sys.exit(1)

    def validate_prerequisites(self):
        """Validate system prerequisites for deployment."""
        # Check if Podman is installed
        try:
            subprocess.run(["podman", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("Podman is installed")
        except subprocess.CalledProcessError:
            logger.error("Podman is not installed. Please install Podman.")
            sys.exit(1)

        # Check if Podman Compose is installed
        try:
            subprocess.run(["podman-compose", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("Podman Compose is installed")
        except subprocess.CalledProcessError:
            logger.error("Podman Compose is not installed. Please install Podman Compose.")
            sys.exit(1)

        # Validate required environment variables
        required_vars = ['OS_VERSION', 'OS_NODE1', 'OS_JAVA_MEM', 'ARKIME_PORT', 'PCAP_DIR']
        for var in required_vars:
            if var not in self.env_vars:
                logger.error(f"Missing required environment variable: {var}")
                sys.exit(1)

        # Validate PCAP directory
        pcap_dir = Path(self.env_vars['PCAP_DIR'])
        if not pcap_dir.exists():
            logger.warning(f"PCAP directory {pcap_dir} does not exist. Creating it...")
            pcap_dir.mkdir(parents=True, exist_ok=True)

        # Validate network interface for capture
        if self.env_vars.get('CAPTURE', 'off') == 'on':
            interface = self.env_vars.get('ARKIME_INTERFACE')
            if not interface:
                logger.error("ARKIME_INTERFACE must be set when CAPTURE is 'on'")
                sys.exit(1)
            interfaces = subprocess.run(
                ["ip", "-o", "link", "show"], capture_output=True, text=True
            ).stdout.splitlines()
            if not any(interface in line for line in interfaces):
                logger.error(f"Network interface {interface} not found")
                sys.exit(1)

    def configure_network(self):
        """Configure /etc/hosts for local DNS resolution."""
        hosts_line = f"127.0.0.1   {self.env_vars['OS_NODE1']} arkime\n"
        try:
            with open('/etc/hosts', 'a') as f:
                f.write(hosts_line)
            logger.info("Updated /etc/hosts with local DNS entries")
        except PermissionError:
            logger.error("Permission denied: Run script with sudo to update /etc/hosts")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to update /etc/hosts: {e}")
            sys.exit(1)

    def deploy_with_compose(self):
        """Deploy Arkime using Podman Compose."""
        logger.info("Starting deployment with Podman Compose...")
        try:
            # Build and start containers
            subprocess.run(self.podman_compose_cmd + ["up", "-d"], check=True)
            logger.info("Arkime deployed successfully with Podman Compose")
        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed: {e}")
            sys.exit(1)

    def deploy_with_kubernetes(self, namespace: str = "arkime"):
        """Deploy Arkime using Kubernetes with Podman-generated manifests."""
        logger.info("Starting deployment with Kubernetes...")
        try:
            # Generate Kubernetes manifests from compose file
            manifest_file = "arkime_k8s_manifest.yaml"
            subprocess.run(self.podman_compose_cmd + ["-f", str(self.compose_file), "config"] + ["--format", "kubernetes", "-o", manifest_file], check=True)
            logger.info(f"Kubernetes manifest generated: {manifest_file}")

            # Apply manifests to Kubernetes
            subprocess.run(["kubectl", "create", "namespace", namespace], check=True, capture_output=True)
            subprocess.run(["kubectl", "apply", "-f", manifest_file, "-n", namespace], check=True)
            logger.info(f"Arkime deployed successfully to Kubernetes namespace {namespace}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Kubernetes deployment failed: {e}")
            sys.exit(1)

    def verify_deployment(self):
        """Verify Arkime deployment by checking container status and logs."""
        logger.info("Verifying deployment...")
        try:
            # Check container status
            result = subprocess.run(
                self.podman_cmd + ["ps", "-a", "--format", "{{.Names}} {{.Status}}"],
                capture_output=True, text=True, check=True
            )
            for line in result.stdout.splitlines():
                logger.info(f"Container status: {line}")

            # Check capture logs if CAPTURE is enabled
            if self.env_vars.get('CAPTURE', 'off') == 'on':
                log_result = subprocess.run(
                    self.podman_cmd + ["exec", "arkime", "cat", "/data/logs/capture.log"],
                    capture_output=True, text=True
                )
                logger.info(f"Capture log: {log_result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Verification failed: {e}")
            sys.exit(1)

    def cleanup(self):
        """Clean up deployment by stopping and removing containers."""
        logger.info("Cleaning up deployment...")
        try:
            subprocess.run(self.podman_compose_cmd + ["down"], check=True)
            logger.info("Deployment cleaned up successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Cleanup failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Deploy Arkime with Podman Compose or Kubernetes")
    parser.add_argument("--compose-file", default="docker-compose.yml", help="Path to docker-compose.yml")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--mode", choices=["compose", "kubernetes"], default="compose", help="Deployment mode")
    parser.add_argument("--namespace", default="arkime", help="Kubernetes namespace (if mode=kubernetes)")
    parser.add_argument("--cleanup", action="store_true", help="Clean up deployment before exiting")
    args = parser.parse_args()

    deployer = ArkimeDeployer(compose_file=args.compose_file, env_file=args.env_file)
    deployer.validate_prerequisites()
    deployer.configure_network()

    if args.mode == "compose":
        deployer.deploy_with_compose()
    else:
        deployer.deploy_with_kubernetes(namespace=args.namespace)

    deployer.verify_deployment()

    if args.cleanup:
        deployer.cleanup()

if __name__ == "__main__":
    main()