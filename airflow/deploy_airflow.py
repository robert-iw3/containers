import os
import subprocess
import argparse
import logging
import yaml
import time
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AirflowDeployer:
    def __init__(self, deploy_type: str, config_path: str = "deploy_config.yaml"):
        self.deploy_type = deploy_type.lower()
        self.config_path = config_path
        self.config = self.load_config()
        self.supported_deployments = ['docker', 'podman', 'kubernetes']

    def load_config(self) -> dict:
        """Load deployment configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_path} not found")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise

    def validate_environment(self) -> bool:
        """Validate required tools are installed based on deployment type."""
        if self.deploy_type not in self.supported_deployments:
            logger.error(f"Unsupported deployment type: {self.deploy_type}")
            return False

        try:
            if self.deploy_type in ['docker', 'podman']:
                subprocess.run([self.deploy_type, '--version'], check=True, capture_output=True)
                subprocess.run([f"{self.deploy_type}-compose", '--version'], check=True, capture_output=True)
            elif self.deploy_type == 'kubernetes':
                subprocess.run(['kubectl', 'version', '--client'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.error(f"Required tool for {self.deploy_type} not found")
            return False
        return True

    def build_image(self) -> bool:
        """Build Airflow Docker image."""
        try:
            cmd = [self.deploy_type, 'build', '-t', f'airflow:{self.config["airflow_version"]}', '.']
            subprocess.run(cmd, check=True)
            logger.info("Airflow image built successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build Airflow image: {e}")
            return False

    def deploy(self) -> bool:
        """Deploy Airflow based on specified deployment type."""
        try:
            if self.deploy_type in ['docker', 'podman']:
                cmd = [f"{self.deploy_type}-compose", 'up', '-d']
                subprocess.run(cmd, check=True)
                logger.info(f"Airflow deployed successfully using {self.deploy_type}")
            elif self.deploy_type == 'kubernetes':
                cmd = ['kubectl', 'apply', '-f', 'k8s-deployment.yaml']
                subprocess.run(cmd, check=True)
                logger.info("Airflow deployed successfully to Kubernetes")
                # Wait for pods to be ready
                self.wait_for_kubernetes_pods()
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def wait_for_kubernetes_pods(self, timeout: int = 300, interval: int = 10) -> None:
        """Wait for Kubernetes pods to be in Running state."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ['kubectl', 'get', 'pods', '-l', 'app=airflow', '-o', 'jsonpath={.items[*].status.phase}'],
                    capture_output=True, text=True, check=True
                )
                pod_statuses = result.stdout.split()
                if all(status == 'Running' for status in pod_statuses):
                    logger.info("All Airflow pods are running")
                    return
                logger.info("Waiting for Airflow pods to be ready...")
                time.sleep(interval)
            except subprocess.CalledProcessError:
                logger.warning("Error checking pod status, retrying...")
                time.sleep(interval)
        logger.error("Timeout waiting for Airflow pods to be ready")
        raise TimeoutError("Airflow pods failed to reach Running state")

    def cleanup(self) -> bool:
        """Cleanup Airflow deployment."""
        try:
            if self.deploy_type in ['docker', 'podman']:
                cmd = [f"{self.deploy_type}-compose", 'down', '--volumes', '--remove-orphans']
                subprocess.run(cmd, check=True)
                logger.info(f"Airflow cleaned up successfully using {self.deploy_type}")
            elif self.deploy_type == 'kubernetes':
                cmd = ['kubectl', 'delete', '-f', 'k8s-deployment.yaml']
                subprocess.run(cmd, check=True)
                logger.info("Airflow Kubernetes resources cleaned up successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Cleanup failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Deploy Airflow using Docker, Podman, or Kubernetes")
    parser.add_argument(
        '--type',
        choices=['docker', 'podman', 'kubernetes'],
        default='docker',
        help='Deployment type'
    )
    parser.add_argument(
        '--config',
        default='deploy_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--action',
        choices=['deploy', 'cleanup'],
        default='deploy',
        help='Action to perform'
    )
    args = parser.parse_args()

    deployer = AirflowDeployer(args.type, args.config)

    if not deployer.validate_environment():
        logger.error("Environment validation failed")
        return

    if args.action == 'deploy':
        if deployer.build_image():
            deployer.deploy()
    elif args.action == 'cleanup':
        deployer.cleanup()

if __name__ == "__main__":
    main()