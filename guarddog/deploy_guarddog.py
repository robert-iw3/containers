import argparse
import subprocess
import os
import logging
import yaml
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GuardDogDeployer:
    def __init__(self, config_file, results_dir, namespace="default"):
        self.config_file = config_file
        self.results_dir = os.path.abspath(results_dir)
        self.namespace = namespace
        self.image_name = "guarddog:latest"
        self.pkgs = []
        self.load_config()

    def load_config(self):
        with open(self.config_file, 'r') as f:
            data = yaml.safe_load(f) or {}

        if not data or 'packages' not in data or not isinstance(data['packages'], list):
            raise ValueError("Invalid or missing 'packages' list in packages.yaml")

        for pkg in data['packages']:
            name = pkg.get('name')
            if not name:
                raise ValueError("Package missing 'name' field")
            ecosystem = pkg.get('ecosystem', 'pypi').lower()
            if ecosystem not in ['pypi', 'npm', 'go', 'github_action', 'extension']:
                raise ValueError(f"Invalid ecosystem: {ecosystem}")
            result_name = pkg.get('result_name', name.replace('/', '_').replace(':', '_').replace('.', '_'))
            self.pkgs.append({"name": name, "ecosystem": ecosystem, "result_name": result_name})

        logging.info(f"Loaded {len(self.pkgs)} packages from {self.config_file}")

    def build_image(self, runtime="podman"):
        logging.info(f"Building GuardDog image with {runtime}...")
        subprocess.run(f"{runtime} build -t {self.image_name} .", shell=True, check=True)

    def scan_packages_container(self, runtime="podman", max_parallel=4, timeout=300):
        container_name = "guarddog-container"
        os.makedirs(self.results_dir, exist_ok=True)

        subprocess.run(
            f"{runtime} run --rm -d --name {container_name} "
            f"--user $(id -u):$(id -g) "
            f"-v {self.results_dir}:/guarddog-results:Z "
            f"{self.image_name} tail -f /dev/null",
            shell=True, check=True
        )

        def scan_one(pkg):
            output_file = os.path.join(self.results_dir, f"{pkg['result_name']}.json")
            cmd = [
                runtime, "exec", container_name,
                "timeout", str(timeout),
                "guarddog", pkg["ecosystem"], "scan", pkg["name"],
                "--output-format=json"
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout + 60)
                with open(output_file, 'w') as f:
                    f.write(result.stdout.strip() + "\n")
                logging.info(f"Success: {pkg['ecosystem']}: {pkg['name']}")
            except Exception as e:
                logging.error(f"Failed: {pkg['ecosystem']}: {pkg['name']} → {e}")
                with open(output_file, 'w') as f:
                    f.write(json.dumps({"error": str(e), "package": pkg["name"]}))

        try:
            with ThreadPoolExecutor(max_workers=max_parallel) as executor:
                futures = [executor.submit(scan_one, pkg) for pkg in self.pkgs]
                for future in as_completed(futures):
                    future.result()
        finally:
            subprocess.run(
                f"{runtime} stop {container_name}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    def deploy_kubernetes(self):
        config.load_kube_config()
        batch_api = client.BatchV1Api()

        for pkg in self.pkgs:
            safe_name = pkg['result_name'].lower().replace('.', '-').replace('_', '-').replace('/', '-').replace(':', '-')
            job_name = f"guarddog-scan-{safe_name}"[:63]

            job_manifest = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": job_name,
                    "namespace": self.namespace
                },
                "spec": {
                    "backoffLimit": 4,
                    "template": {
                        "spec": {
                            "restartPolicy": "Never",
                            "containers": [{
                                "name": "guarddog",
                                "image": self.image_name,
                                "command": ["guarddog", pkg['ecosystem'], "scan", pkg['name'], "--output-format=json"],
                                "volumeMounts": [{"name": "results", "mountPath": "/guarddog-results"}],
                                "securityContext": {"runAsNonRoot": True, "runAsUser": 1000}
                            }],
                            "volumes": [{
                                "name": "results",
                                "hostPath": {
                                    "path": self.results_dir,
                                    "type": "DirectoryOrCreate"
                                }
                            }]
                        }
                    }
                }
            }

            try:
                batch_api.create_namespaced_job(namespace=self.namespace, body=job_manifest)
                logging.info(f"Created Kubernetes Job: {job_name}")
            except ApiException as e:
                if e.status == 409:
                    logging.warning(f"Job already exists: {job_name}")
                else:
                    logging.error(f"Kubernetes error: {e}")

def main():
    parser = argparse.ArgumentParser(description="GuardDog Multi-Platform Deployer")
    parser.add_argument("--runtime", choices=["docker", "podman", "kubernetes", "ansible"], required=True)
    parser.add_argument("--config", default="packages.yaml")
    parser.add_argument("--results-dir", default="./guarddog-results")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--inventory", default="inventory.yml")
    parser.add_argument("--container-runtime", choices=["docker", "podman"], default="podman")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)

    args = parser.parse_args()

    deployer = GuardDogDeployer(args.config, args.results_dir, args.namespace)

    runtime_to_use = args.container_runtime

    if args.runtime in ["docker", "podman"]:
        runtime_to_use = args.runtime
        deployer.build_image(runtime_to_use)
        deployer.scan_packages_container(runtime=runtime_to_use, max_parallel=args.max_parallel, timeout=args.timeout)
    elif args.runtime == "kubernetes":
        deployer.build_image(runtime_to_use)
        deployer.deploy_kubernetes()
    elif args.runtime == "ansible":
        cmd = f"ansible-playbook -i {args.inventory} deploy_guarddog.yml --extra-vars \"container_runtime={runtime_to_use}\""
        subprocess.run(cmd, shell=True, check=True)

if __name__ == "__main__":
    main()