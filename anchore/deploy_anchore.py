#!/usr/bin/env python3

"""
Anchore Container Image Scanner Deployment Script
Supports deployment via Podman or Kubernetes.
Generates SBOMs and vulnerability reports in multiple formats.

RW
"""

import subprocess
import logging
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import argparse
from tqdm import tqdm
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'anchore_scan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AnchoreScanner:
    def __init__(self, config_file="scan_config.json", output_dir="./scan_results", max_workers=4, deploy_type="podman"):
        self.config_file = Path(config_file)
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.deploy_type = deploy_type.lower()
        self.container_name = "anchore"
        self.output_dir.mkdir(exist_ok=True)
        self.image_configs = self.load_config()
        self.batch_size = 10  # Process images in batches for memory efficiency

    def load_config(self):
        """Load image configurations from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config.get("images", [])
        except FileNotFoundError:
            logger.error(f"Config file {self.config_file} not found")
            raise
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in config file {self.config_file}")
            raise

    def run_command(self, command, error_message="Command failed"):
        """Execute a shell command and handle errors"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                text=True,
                capture_output=True
            )
            logger.info(f"Command executed successfully: {command}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"{error_message}: {e.stderr}")
            raise

    def deploy_podman(self):
        """Deploy using Podman"""
        logger.info("Building Anchore container with Podman...")
        self.run_command(
            "podman build -t anchore .",
            "Failed to build Anchore container"
        )

        logger.info("Pruning unused images...")
        self.run_command(
            "podman image prune -f",
            "Failed to prune images"
        )

        logger.info("Starting Anchore container...")
        self.run_command(
            f"podman run --rm -it --name {self.container_name} -d anchore",
            "Failed to start Anchore container"
        )

    def deploy_kubernetes(self):
        """Deploy using Kubernetes"""
        logger.info("Applying Kubernetes deployment...")
        try:
            # Ensure namespace exists
            self.run_command(
                "kubectl create namespace anchore --dry-run=client -o yaml | kubectl apply -f -",
                "Failed to create namespace"
            )

            # Apply the deployment YAML
            with open("anchore-deployment.yaml", 'w') as f:
                yaml.dump(self.generate_k8s_deployment(), f, default_flow_style=False)

            self.run_command(
                "kubectl apply -f anchore-deployment.yaml",
                "Failed to apply Kubernetes deployment"
            )

            # Wait for pod to be ready
            self.run_command(
                "kubectl wait --for=condition=ready pod -l app=anchore-scanner -n anchore --timeout=300s",
                "Failed to wait for pod readiness"
            )
        except Exception as e:
            logger.error(f"Kubernetes deployment failed: {str(e)}")
            raise

    def generate_k8s_deployment(self):
        """Generate Kubernetes deployment YAML dynamically from image configs"""
        job_commands = []
        for config in self.image_configs:
            repo = config["repo"]
            name = config["name"]
            job_commands.extend([
                f"syft {repo} --scope all-layers -o syft-json=/home/anchore/{name}_SBOM.json",
                f"syft {repo} --scope all-layers -o syft-table=/home/anchore/{name}_SBOM.csv",
                f"grype {repo} -o json --file /home/anchore/{name}_vulnerabilities.json",
                f"grype {repo} -o table --file /home/anchore/{name}_vulnerabilities.csv"
            ])

        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": "anchore-scan-job",
                "namespace": "anchore"
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "anchore-scanner",
                            "image": "anchore:latest",
                            "imagePullPolicy": "IfNotPresent",
                            "command": ["/bin/sh", "-c"],
                            "args": [" && ".join(job_commands)],
                            "volumeMounts": [{
                                "name": "scan-results",
                                "mountPath": "/home/anchore"
                            }],
                            "resources": {
                                "limits": {"cpu": "2", "memory": "4Gi"},
                                "requests": {"cpu": "1", "memory": "2Gi"}
                            }
                        }],
                        "restartPolicy": "Never",
                        "volumes": [{
                            "name": "scan-results",
                            "persistentVolumeClaim": {"claimName": "anchore-scan-results"}
                        }]
                    }
                }
            }
        }

    def scan_image(self, image_config, output_format, extension):
        """Scan a single image with specified output format"""
        repo = image_config["repo"]
        name = image_config["name"]
        output_file = f"{self.output_dir}/{name}_SBOM_{output_format}.{extension}"

        if self.deploy_type == "podman":
            cmd = (
                f"podman exec -it {self.container_name} syft {repo} "
                f"--scope all-layers -o {output_format}={output_file}"
            )
        else:
            cmd = (
                f"kubectl exec -n anchore $(kubectl get pod -n anchore -l app=anchore-scanner -o jsonpath='{{.items[0].metadata.name}}') -- "
                f"syft {repo} --scope all-layers -o {output_format}=/home/anchore/{name}_SBOM_{output_format}.{extension}"
            )

        logger.info(f"Scanning {repo} with format {output_format}")
        self.run_command(cmd, f"Failed to scan {repo} with format {output_format}")

        return f"Completed {output_format} scan for {repo}"

    def scan_vulnerabilities(self, image_config, output_format, extension):
        """Scan vulnerabilities for a single image"""
        repo = image_config["repo"]
        name = image_config["name"]
        output_file = f"{self.output_dir}/{name}_vulnerabilities.{extension}"

        if self.deploy_type == "podman":
            cmd = (
                f"podman exec -it {self.container_name} grype {repo} "
                f"-o {output_format} --file {output_file}"
            )
        else:
            cmd = (
                f"kubectl exec -n anchore $(kubectl get pod -n anchore -l app=anchore-scanner -o jsonpath='{{.items[0].metadata.name}}') -- "
                f"grype {repo} -o {output_format} --file /home/anchore/{name}_vulnerabilities.{extension}"
            )

        logger.info(f"Scanning vulnerabilities for {repo} with format {output_format}")
        self.run_command(cmd, f"Failed to scan vulnerabilities for {repo}")

        return f"Completed vulnerability scan for {repo} with format {output_format}"

    def run_scans(self):
        """Run all scans in batches with progress tracking"""
        try:
            if self.deploy_type == "podman":
                self.deploy_podman()
            else:
                self.deploy_kubernetes()

            scan_tasks = [
                (self.scan_image, config, "syft-json", "json")
                for config in self.image_configs
            ] + [
                (self.scan_image, config, "syft-table", "csv")
                for config in self.image_configs
            ] + [
                (self.scan_vulnerabilities, config, "json", "json")
                for config in self.image_configs
            ] + [
                (self.scan_vulnerabilities, config, "table", "csv")
                for config in self.image_configs
            ]

            # Process in batches
            for i in range(0, len(scan_tasks), self.batch_size):
                batch = scan_tasks[i:i + self.batch_size]
                logger.info(f"Processing batch {i//self.batch_size + 1} of {len(scan_tasks)//self.batch_size + 1}")

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = [
                        executor.submit(task[0], task[1], task[2], task[3])
                        for task in batch
                    ]

                    for future in tqdm(as_completed(futures), total=len(futures), desc="Scanning"):
                        try:
                            result = future.result()
                            logger.info(result)
                        except Exception as e:
                            logger.error(f"Scan task failed: {str(e)}")

            # Copy results
            logger.info("Copying scan results...")
            if self.deploy_type == "podman":
                self.run_command(
                    f"podman cp {self.container_name}:/home/anchore {self.output_dir}",
                    "Failed to copy scan results"
                )
            else:
                self.run_command(
                    f"kubectl cp anchore/$(kubectl get pod -n anchore -l app=anchore-scanner -o jsonpath='{{.items[0].metadata.name}}'):/home/anchore {self.output_dir}",
                    "Failed to copy Kubernetes results"
                )

        finally:
            # Cleanup
            logger.info("Cleaning up...")
            if self.deploy_type == "podman":
                self.run_command(
                    f"podman rm -f {self.container_name}",
                    "Failed to remove container"
                )
                self.run_command(
                    "podman rmi -f anchore",
                    "Failed to remove image"
                )
            else:
                self.run_command(
                    "kubectl delete -f anchore-deployment.yaml",
                    "Failed to cleanup Kubernetes deployment"
                )

    def generate_summary(self):
        """Generate a summary of scan results"""
        summary = {"scans": [], "timestamp": datetime.now().isoformat(), "deploy_type": self.deploy_type}
        for config in self.image_configs:
            scan_info = {
                "image": config["repo"],
                "name": config["name"],
                "files": []
            }
            for file in self.output_dir.glob(f"{config['name']}*"):
                scan_info["files"].append({
                    "name": file.name,
                    "size": file.stat().st_size,
                    "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                })
            summary["scans"].append(scan_info)

        summary_file = self.output_dir / "scan_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Generated scan summary: {summary_file}")

def main():
    parser = argparse.ArgumentParser(description="Anchore container image scanner")
    parser.add_argument("--deploy-type", choices=["podman", "kubernetes"], default="podman",
                        help="Deployment type: podman or kubernetes")
    parser.add_argument("--config", default="scan_config.json",
                        help="Path to configuration file")
    parser.add_argument("--output-dir", default="./scan_results",
                        help="Output directory for scan results")
    parser.add_argument("--max-workers", type=int, default=4,
                        help="Maximum number of concurrent workers")

    args = parser.parse_args()

    scanner = AnchoreScanner(
        config_file=args.config,
        output_dir=args.output_dir,
        max_workers=args.max_workers,
        deploy_type=args.deploy_type
    )
    scanner.run_scans()
    scanner.generate_summary()

if __name__ == "__main__":
    main()