#!/usr/bin/env python3

import os
import subprocess
import argparse
import yaml
import json
import logging
import requests
import tarfile
import shutil
from pathlib import Path
import docker
from kubernetes import client, config
import ansible_runner
from yaml.loader import SafeLoader
from datetime import datetime

class APIFirewallDeployer:
    def __init__(self, config_file, deploy_type, verbose=False):
        self.config_file = Path(config_file)
        self.deploy_type = deploy_type.lower()
        self.verbose = verbose
        self.setup_logging()
        self.config = self.load_config()
        self.output_dir = Path(self.config["output_dir"]).resolve()
        self.config_dir = self.output_dir / self.config["config_dir"]
        self.openapi_specs = [self.output_dir / spec for spec in self.config.get("openapi_specs", [self.config["openapi_spec"]])]
        self.certs_dir = self.output_dir / self.config["certs_dir"]
        self.crs_dir = self.output_dir / self.config["crs_dir"]
        self.docker_compose_file = self.config_dir / self.config["docker_compose_file"]
        self.allowed_iplist_file = self.config_dir / self.config["allowed_iplist_file"]
        self.coraza_conf_file = self.config_dir / self.config["coraza_conf_file"]
        self.entrypoint_file = self.config_dir / self.config["entrypoint_file"]
        self.dockerfile = self.config_dir / self.config["dockerfile"]
        self.csr_conf_file = self.config_dir / self.config["csr_conf_file"]
        self.ca_csr_conf_file = self.config_dir / self.config["ca_csr_conf_file"]
        self.ansible_playbook = self.config_dir / self.config["ansible_playbook"]

    def setup_logging(self):
        """Configure logging with timestamps and levels"""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Load and validate config.yaml using SafeLoader"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        with open(self.config_file, "r") as f:
            config = yaml.load(f, Loader=SafeLoader)
        if not isinstance(config, dict):
            raise ValueError(f"Invalid {self.config_file}: must be a valid YAML dictionary")
        required_keys = [
            "output_dir", "config_dir", "openapi_spec", "certs_dir", "crs_dir",
            "crs_url", "crs_file", "docker_compose_file", "allowed_iplist_file",
            "coraza_conf_file", "entrypoint_file", "dockerfile", "csr_conf_file",
            "ca_csr_conf_file", "ansible_playbook", "api_fw_url", "server_url",
            "api_spec_path"
        ]
        for key in required_keys:
            if key not in config or config[key] is None:
                raise KeyError(f"Missing or null configuration key: {key}")
        # Override with environment variables
        for key in config:
            env_key = f"APIFW_{key.upper()}"
            if env_key in os.environ:
                config[key] = os.environ[env_key]
        return config

    def validate_openapi_spec(self):
        """Validate OpenAPI specification format"""
        self.logger.info("Validating OpenAPI specification(s)...")
        for spec in self.openapi_specs:
            if not spec.exists():
                raise FileNotFoundError(f"OpenAPI specification {spec} not found")
            try:
                with open(spec, "r") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid OpenAPI specification {spec}: {e}")

    def check_config_files(self):
        """Validate existence and permissions of configuration files"""
        self.logger.info("Validating configuration files...")
        required_files = [
            self.docker_compose_file,
            self.allowed_iplist_file,
            self.coraza_conf_file,
            self.entrypoint_file,
            self.dockerfile,
            self.csr_conf_file,
            self.ca_csr_conf_file,
            self.ansible_playbook
        ]
        for file in required_files:
            if not file.exists():
                raise FileNotFoundError(f"Required configuration file {file} not found in {self.config_dir}")
            if not os.access(file, os.R_OK):
                raise PermissionError(f"Configuration file {file} is not readable")
        self.validate_openapi_spec()
        if not os.access(self.entrypoint_file, os.X_OK):
            raise PermissionError(f"{self.entrypoint_file} is not executable. Run: chmod +x {self.entrypoint_file}")

    def check_dependencies(self):
        """Validate runtime dependencies"""
        self.logger.info("Checking runtime dependencies...")
        dependencies = {
            "docker": ["docker", "--version"],
            "podman": ["podman", "--version"],
            "kubectl": ["kubectl", "version", "--client"],
            "ansible": ["ansible", "--version"],
            "kompose": ["kompose", "version"]
        }
        required_tool = "docker" if self.deploy_type == "docker" else self.deploy_type
        if self.deploy_type in ["docker", "kubernetes"]:
            try:
                subprocess.run(dependencies[required_tool], check=True, capture_output=True, text=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(f"Required tool {required_tool} not found: {e}")
        if self.deploy_type == "kubernetes":
            try:
                subprocess.run(dependencies["kompose"], check=True, capture_output=True, text=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(f"Kompose not found: {e}")
        if self.deploy_type == "ansible":
            try:
                subprocess.run(dependencies["ansible"], check=True, capture_output=True, text=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(f"Ansible not found: {e}")

    def generate_ssl_certificates(self):
        """Generate SSL certificates using api-fw-csr.conf and ca-csr.conf"""
        self.logger.info("Generating SSL certificates...")
        self.certs_dir.mkdir(mode=0o700, exist_ok=True)
        os.chdir(self.certs_dir)
        try:
            subprocess.run(["openssl", "genrsa", "-out", "ca.key.pem", "4096"], check=True)
            subprocess.run([
                "openssl", "req", "-new", "-x509", "-days", "730", "-key", "ca.key.pem",
                "-config", str(self.ca_csr_conf_file), "-out", "ca.crt.pem"
            ], check=True)
            subprocess.run(["openssl", "genrsa", "-out", "api-fw.key.pem", "4096"], check=True)
            subprocess.run([
                "openssl", "req", "-new", "-key", "api-fw.key.pem", "-out", "api-fw.csr",
                "-config", str(self.csr_conf_file)
            ], check=True)
            subprocess.run([
                "openssl", "x509", "-req", "-in", "api-fw.csr", "-CA", "ca.crt.pem",
                "-CAkey", "ca.key.pem", "-CAcreateserial", "-sha512", "-out", "api-fw.crt.pem",
                "-days", "365", "-extfile", str(self.csr_conf_file)
            ], check=True)
            for pem in ["ca.key.pem", "api-fw.key.pem", "ca.crt.pem", "api-fw.crt.pem"]:
                if os.path.exists(pem):
                    os.chmod(pem, 0o640)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"SSL certificate generation failed: {e}")
        finally:
            os.chdir(self.output_dir)

    def download_crs(self):
        """Download and extract OWASP Core Rule Set"""
        self.logger.info("Downloading OWASP Core Rule Set...")
        crs_path = self.output_dir / self.config["crs_file"]
        try:
            if not crs_path.exists():
                response = requests.get(self.config["crs_url"], stream=True, timeout=30)
                response.raise_for_status()
                with open(crs_path, "wb") as f:
                    f.write(response.content)
            if not self.crs_dir.exists():
                self.crs_dir.mkdir(mode=0o755)
                with tarfile.open(crs_path, "r:gz") as tar:
                    members = [m for m in tar.getmembers() if m.name.startswith("coreruleset-4.18.0/")]
                    for member in members:
                        member.mode = 0o644 if member.isfile() else 0o755
                        tar.extract(member, self.crs_dir)
                    for item in (self.crs_dir / "coreruleset-4.18.0").glob("*"):
                        shutil.move(str(item), str(self.crs_dir))
                    shutil.rmtree(self.crs_dir / "coreruleset-4.18.0")
        except (requests.RequestException, tarfile.TarError) as e:
            raise RuntimeError(f"Failed to download or extract CRS: {e}")

    def deploy_docker(self):
        """Deploy using Docker or Podman"""
        self.logger.info("Deploying with Docker/Podman...")
        try:
            client = docker.from_env()
            subprocess.run(["podman-compose", "up", "-d", "--force-recreate"], cwd=self.output_dir,
                          check=True, capture_output=True, text=True)
            self.logger.info("Deployment successful. Run 'podman-compose logs -f' to check logs.")
        except (subprocess.CalledProcessError, docker.errors.DockerException) as e:
            raise RuntimeError(f"Docker/Podman deployment failed: {e}")

    def deploy_kubernetes(self):
        """Deploy using Kubernetes"""
        self.logger.info("Deploying with Kubernetes...")
        try:
            config.load_kube_config()
            k8s_dir = self.output_dir / "k8s"
            k8s_dir.mkdir(mode=0o755, exist_ok=True)
            subprocess.run(["kompose", "convert", "-f", str(self.docker_compose_file), "--out", "k8s"],
                          cwd=self.output_dir, check=True, capture_output=True, text=True)
            for manifest in k8s_dir.glob("*.yaml"):
                subprocess.run(["kubectl", "apply", "-f", str(manifest)], check=True, capture_output=True, text=True)
            self.logger.info("Kubernetes deployment successful. Run 'kubectl logs <pod-name>' to check logs.")
        except (subprocess.CalledProcessError, config.ConfigException) as e:
            raise RuntimeError(f"Kubernetes deployment failed: {e}")

    def deploy_ansible(self):
        """Deploy using Ansible"""
        self.logger.info("Deploying with Ansible...")
        try:
            result = ansible_runner.run(
                private_data_dir=str(self.output_dir),
                playbook=str(self.ansible_playbook),
                extravars={"output_dir": str(self.output_dir)},
                quiet=not self.verbose
            )
            if result.rc != 0:
                raise RuntimeError(f"Ansible deployment failed: {result.stats}")
            self.logger.info("Ansible deployment successful. Run 'podman-compose logs -f' to check logs.")
        except Exception as e:
            raise RuntimeError(f"Ansible deployment failed: {e}")

    def deploy(self):
        """Orchestrate the deployment process"""
        self.logger.info("Starting API Firewall deployment...")
        self.check_config_files()
        self.check_dependencies()
        self.generate_ssl_certificates()
        self.download_crs()
        if self.deploy_type == "docker":
            self.deploy_docker()
        elif self.deploy_type == "kubernetes":
            self.deploy_kubernetes()
        elif self.deploy_type == "ansible":
            self.deploy_ansible()
        else:
            raise ValueError(f"Unsupported deployment type: {self.deploy_type}")

def main():
    parser = argparse.ArgumentParser(description="Deploy Wallarm API Firewall")
    parser.add_argument("--config-file", default="config/config.yaml", help="Path to configuration file")
    parser.add_argument("--deploy-type", choices=["docker", "kubernetes", "ansible"], required=True, help="Deployment type")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    try:
        deployer = APIFirewallDeployer(args.config_file, args.deploy_type, args.verbose)
        deployer.deploy()
    except Exception as e:
        logging.error(f"Deployment failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()