import os
import subprocess
import yaml
import argparse
import logging
import json
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import ansible_runner

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FlinkDeployer:
    def __init__(self, config_path="flink_config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.flink_version = self.config.get('flink_version', '2.0.0')
        self.namespace = self.config.get('namespace', 'flink')
        self.container_engine = self.config.get('container_engine', 'docker')

    def load_config(self):
        """Load and validate configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Validate TLS certificates if enabled
            if config.get('security', {}).get('enable_tls', False):
                cert_path = config['security'].get('cert_path')
                if not cert_path:
                    logger.error("TLS enabled but cert_path not specified in config")
                    raise ValueError("Missing cert_path in configuration")
                if not os.path.exists(os.path.join(cert_path, 'keystore.jks')) or \
                   not os.path.exists(os.path.join(cert_path, 'truststore.jks')):
                    logger.error("TLS enabled but keystore.jks or truststore.jks not found")
                    raise ValueError("Missing TLS certificates")

            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_path} not found")
            raise

    def check_prerequisites(self):
        """Check if required tools are installed"""
        tools = ['docker', 'podman', 'kubectl', 'ansible', 'ansible-playbook']
        for tool in tools:
            try:
                subprocess.run([tool, '--version'], check=True, capture_output=True)
                logger.info(f"{tool} is installed")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(f"{tool} is not installed or not working properly")

    def build_container(self):
        """Build Flink container image using specified engine"""
        engine = self.container_engine
        logger.info(f"Building Flink container image using {engine}")

        try:
            # Enable BuildKit for Docker
            env = os.environ.copy()
            if engine == 'docker':
                env['DOCKER_BUILDKIT'] = '1'
            cmd = [engine, 'build', '-t', f'flink:{self.flink_version}', '-f', 'Dockerfile', '.']
            subprocess.run(cmd, check=True, env=env)
            logger.info(f"Successfully built Flink {self.flink_version} image")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build container image: {e}")
            raise

    def deploy_kubernetes(self):
        """Deploy Flink to Kubernetes"""
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()
            apps_v1 = client.AppsV1Api()

            # Create namespace if it doesn't exist
            try:
                v1.read_namespace(self.namespace)
            except ApiException as e:
                if e.status == 404:
                    namespace_body = client.V1Namespace(metadata=client.V1ObjectMeta(name=self.namespace))
                    v1.create_namespace(namespace_body)
                    logger.info(f"Created namespace {self.namespace}")

            # Apply Kubernetes manifests
            with open('flink-deployment.yaml', 'r') as f:
                deployment = yaml.safe_load(f)
            with open('flink-service.yaml', 'r') as f:
                service = yaml.safe_load(f)

            apps_v1.create_namespaced_deployment(namespace=self.namespace, body=deployment)
            v1.create_namespaced_service(namespace=self.namespace, body=service)

            logger.info(f"Deployed Flink to Kubernetes namespace {self.namespace}")
        except Exception as e:
            logger.error(f"Failed to deploy to Kubernetes: {e}")
            raise

    def run_ansible_playbook(self):
        """Run Ansible playbook for additional configuration"""
        logger.info("Running Ansible playbook for Flink configuration")

        try:
            r = ansible_runner.run(
                private_data_dir='.',
                playbook='flink-playbook.yaml',
                extravars={
                    'flink_version': self.flink_version,
                    'namespace': self.namespace,
                    'enable_tls': self.config.get('security', {}).get('enable_tls', False),
                    'cert_path': self.config.get('security', {}).get('cert_path', '/etc/flink/certs')
                }
            )
            if r.rc == 0:
                logger.info("Ansible playbook executed successfully")
            else:
                logger.error(f"Ansible playbook failed with status: {r.rc}")
                raise RuntimeError("Ansible playbook execution failed")
        except Exception as e:
            logger.error(f"Ansible playbook execution failed: {e}")
            raise

    def verify_deployment(self):
        """Verify Flink deployment status"""
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()

            pods = v1.list_namespaced_pod(namespace=self.namespace, label_selector="app=flink")
            for pod in pods.items:
                logger.info(f"Pod {pod.metadata.name} status: {pod.status.phase}")
                if pod.status.phase != "Running":
                    logger.warning(f"Pod {pod.metadata.name} is not in Running state")

            services = v1.list_namespaced_service(namespace=self.namespace, label_selector="app=flink")
            for service in services.items:
                logger.info(f"Service {service.metadata.name} is running")

            # Verify healthcheck
            for pod in pods.items:
                pod_name = pod.metadata.name
                cmd = f"kubectl exec -n {self.namespace} {pod_name} -- curl -f http://localhost:8081"
                try:
                    subprocess.run(cmd, shell=True, check=True, capture_output=True)
                    logger.info(f"Healthcheck passed for pod {pod_name}")
                except subprocess.CalledProcessError:
                    logger.warning(f"Healthcheck failed for pod {pod_name}")
        except Exception as e:
            logger.error(f"Deployment verification failed: {e}")
            raise

    def deploy(self):
        """Main deployment method"""
        try:
            self.check_prerequisites()
            self.build_container()
            self.deploy_kubernetes()
            self.run_ansible_playbook()
            self.verify_deployment()
            logger.info("Flink deployment completed successfully")
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Apache Flink Deployment Automation")
    parser.add_argument('--config', default='flink_config.yaml', help='Path to configuration file')
    args = parser.parse_args()

    deployer = FlinkDeployer(args.config)
    deployer.deploy()

if __name__ == '__main__':
    main()