#!/usr/bin/env python3
"""
Defguard quick setup script.
Automates the deployment of defguard using Docker or Podman with Compose support.
Generates SSL certificates, RSA keys, and configures the environment.
Randomized Passwords: The script generates random passwords for DEFGUARD_DB_PASSWORD
and DEFGUARD_DEFAULT_ADMIN_PASSWORD unless specified in the .env file or environment
variables. These are displayed in the deployment summary.

RW

python3 setup.py --config-file config.yaml
"""

import argparse
import json
import logging
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List
import yaml
from tqdm import tqdm
from dotenv import load_dotenv

# Constants
VERSION = "1.2.1"
SECRET_LENGTH = 64
PASSWORD_LENGTH = 16
VOLUME_DIR = ".volumes"
SSL_DIR = f"{VOLUME_DIR}/ssl"
RSA_DIR = f"{VOLUME_DIR}/core"
COMPOSE_FILE = "docker-compose.yml"
ENV_FILE = ".env"
BASE_COMPOSE_FILE_URL = "https://raw.githubusercontent.com/robert-iw3/containers/refs/heads/main/defguard/docker-compose.yml"
BASE_ENV_FILE_URL = "https://raw.githubusercontent.com/robert-iw3/containers/refs/heads/main/defguard/.env"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"setup.log.{os.urandom(4).hex()}", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DefguardConfig:
    """Class to hold and validate defguard configuration."""
    def __init__(self):
        self.domain: Optional[str] = None
        self.enrollment_domain: Optional[str] = None
        self.use_https: bool = False
        self.volume_dir: str = VOLUME_DIR
        self.vpn_name: Optional[str] = None
        self.vpn_ip: Optional[str] = None
        self.vpn_gateway_ip: Optional[str] = None
        self.vpn_gateway_port: Optional[str] = None
        self.dev: bool = False
        self.pre_release: bool = False
        self.non_interactive: bool = False
        self.defguard_url: Optional[str] = None
        self.enrollment_url: Optional[str] = None
        self.enable_vpn: bool = False
        self.enable_enrollment: bool = False
        self.db_password: Optional[str] = None
        self.admin_password: Optional[str] = None

    def validate(self):
        """Validate required configuration options."""
        if not self.domain:
            raise ValueError("CFG_DOMAIN is required")
        if self.vpn_name:
            self.enable_vpn = True
            for field in ["vpn_ip", "vpn_gateway_ip", "vpn_gateway_port"]:
                if not getattr(self, field):
                    raise ValueError(f"{field.upper()} is required when VPN is enabled")
        if self.enrollment_domain:
            self.enable_enrollment = True

    def generate_urls(self):
        """Generate external URLs based on configuration."""
        protocol = "https" if self.use_https else "http"
        self.defguard_url = f"{protocol}://{self.domain}"
        if self.enrollment_domain:
            self.enrollment_url = f"{protocol}://{self.enrollment_domain}"

class DefguardDeployer:
    """Class to handle defguard deployment."""
    def __init__(self, config: DefguardConfig):
        self.config = config
        self.work_dir = Path.cwd()
        self.compose_file = self.work_dir / COMPOSE_FILE
        self.env_file = self.work_dir / ENV_FILE
        self.container_runtime, self.compose_cmd = self._detect_container_runtime()
        self.image_type_name = "latest production"
        self.core_image_tag = "latest"
        self.gateway_image_tag = "latest"
        self.proxy_image_tag = "latest"

    def _detect_container_runtime(self) -> tuple[str, str]:
        """Detect if Docker or Podman is available and set Compose command."""
        for runtime in ["docker", "podman"]:
            try:
                subprocess.run([runtime, "--version"], check=True, capture_output=True)
                try:
                    subprocess.run([runtime, "compose", "version"], check=True, capture_output=True)
                    return runtime, f"{runtime} compose"
                except subprocess.CalledProcessError:
                    if runtime == "docker":
                        if subprocess.run(["docker-compose", "--version"], check=True, capture_output=True):
                            return runtime, "docker-compose"
                    elif runtime == "podman":
                        if subprocess.run(["podman-compose", "--version"], check=True, capture_output=True):
                            return runtime, "podman-compose"
            except subprocess.CalledProcessError:
                continue
        raise RuntimeError("Neither Docker nor Podman with Compose support found")

    def check_environment(self):
        """Check if required tools and directories are available."""
        logger.info("Checking environment...")
        for cmd in ["openssl", "curl", "grep"]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                raise RuntimeError(f"{cmd} command not found")

        volume_dir = Path(self.config.volume_dir).resolve()
        for dir_path in [volume_dir, volume_dir / "ssl", volume_dir / "core"]:
            if dir_path.exists():
                raise RuntimeError(f"Directory {dir_path} already exists")
            dir_path.mkdir(parents=True)
        if self.compose_file.exists():
            raise RuntimeError(f"Docker compose file {self.compose_file} already exists")

    def setup_docker_image_version(self):
        """Set Docker image versions based on configuration."""
        if self.config.dev:
            self.image_type_name = "development"
            self.core_image_tag = self.gateway_image_tag = self.proxy_image_tag = "dev"
        elif self.config.pre_release:
            self.image_type_name = "pre-release"
            self.core_image_tag = self.gateway_image_tag = self.proxy_image_tag = "pre-release"
        logger.info(f"Using {self.image_type_name} {self.container_runtime} images")

    def generate_secret(self, length: int = SECRET_LENGTH) -> str:
        """Generate a random secret."""
        cmd = f"openssl rand -base64 {length} | tr -d '=+/\\n' | cut -c1-{length-1}"
        return subprocess.check_output(cmd, shell=True, text=True)

    def generate_certs(self):
        """Generate SSL certificates."""
        ssl_dir = Path(self.config.volume_dir) / "ssl"
        passphrase = self.generate_secret()
        logger.info(f"Generating SSL certificates in {ssl_dir}...")

        # Generate CA private key
        subprocess.run([
            "openssl", "genrsa", "-des3", "-out", str(ssl_dir / "defguard-ca.key"),
            "-passout", f"pass:{passphrase}", "2048"
        ], check=True)

        # Generate Root Certificate
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes", "-key", str(ssl_dir / "defguard-ca.key"),
            "-sha256", "-days", "1825", "-out", str(ssl_dir / "defguard-ca.pem"),
            "-passin", f"pass:{passphrase}", "-subj",
            f"/C=PL/ST=Zachodniopomorskie/L=Szczecin/O=Example/OU=IT Department/CN={self.config.domain}"
        ], check=True)

        # Generate CA-signed certificate for defguard gRPC
        subprocess.run([
            "openssl", "genrsa", "-out", str(ssl_dir / "defguard-grpc.key"), "2048"
        ], check=True)
        subprocess.run([
            "openssl", "req", "-new", "-key", str(ssl_dir / "defguard-grpc.key"),
            "-out", str(ssl_dir / "defguard-grpc.csr"),
            "-subj", f"/C=PL/ST=Zachodniopomorskie/L=Szczecin/O=Example/OU=IT Department/CN={self.config.domain}"
        ], check=True)
        with open(ssl_dir / "defguard-grpc.ext", "w") as f:
            f.write(f"""authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = {self.config.domain}
DNS.2 = core
DNS.3 = localhost
""")
        subprocess.run([
            "openssl", "x509", "-req", "-in", str(ssl_dir / "defguard-grpc.csr"),
            "-CA", str(ssl_dir / "defguard-ca.pem"), "-CAkey", str(ssl_dir / "defguard-ca.key"),
            "-passin", f"pass:{passphrase}", "-CAcreateserial",
            "-out", str(ssl_dir / "defguard-grpc.crt"), "-days", "1000", "-sha256",
            "-extfile", str(ssl_dir / "defguard-grpc.ext")
        ], check=True)

        # Generate CA-signed certificate for proxy gRPC
        subprocess.run([
            "openssl", "genrsa", "-out", str(ssl_dir / "defguard-proxy-grpc.key"), "2048"
        ], check=True)
        subprocess.run([
            "openssl", "req", "-new", "-key", str(ssl_dir / "defguard-proxy-grpc.key"),
            "-out", str(ssl_dir / "defguard-proxy-grpc.csr"),
            "-subj", f"/C=PL/ST=Zachodniopomorskie/L=Szczecin/O=Example/OU=IT Department/CN={self.config.domain}"
        ], check=True)
        with open(ssl_dir / "defguard-proxy-grpc.ext", "w") as f:
            f.write(f"""authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = proxy
DNS.2 = localhost
""")
        subprocess.run([
            "openssl", "x509", "-req", "-in", str(ssl_dir / "defguard-proxy-grpc.csr"),
            "-CA", str(ssl_dir / "defguard-ca.pem"), "-CAkey", str(ssl_dir / "defguard-ca.key"),
            "-passin", f"pass:{passphrase}", "-CAcreateserial",
            "-out", str(ssl_dir / "defguard-proxy-grpc.crt"), "-days", "1000", "-sha256",
            "-extfile", str(ssl_dir / "defguard-proxy-grpc.ext")
        ], check=True)

    def generate_rsa(self):
        """Generate RSA keys."""
        rsa_dir = Path(self.config.volume_dir) / "core"
        logger.info(f"Generating RSA keys in {rsa_dir}...")
        subprocess.run([
            "openssl", "genpkey", "-out", str(rsa_dir / "rsakey.pem"),
            "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"
        ], check=True)

    def setup_keys(self):
        """Setup SSL certificates and RSA keys."""
        ssl_dir = Path(self.config.volume_dir) / "ssl"
        rsa_dir = Path(self.config.volume_dir) / "core"
        if ssl_dir.exists() and any(ssl_dir.iterdir()):
            logger.info(f"Using existing SSL certificates from {ssl_dir}")
        else:
            self.generate_certs()
        if rsa_dir.exists() and any(rsa_dir.iterdir()):
            logger.info(f"Using existing RSA keys from {rsa_dir}")
        else:
            self.generate_rsa()

    def create_caddyfile(self):
        """Generate Caddyfile for reverse proxy."""
        caddy_dir = Path(self.config.volume_dir) / "caddy"
        caddyfile = caddy_dir / "Caddyfile"
        caddy_dir.mkdir(parents=True, exist_ok=True)
        with open(caddyfile, "w") as f:
            f.write(f"{self.config.defguard_url} {{\n\treverse_proxy core:8000\n}}\n\n")
            if self.config.enable_enrollment:
                f.write(f"{self.config.enrollment_url} {{\n\treverse_proxy proxy:8080\n}}\n\n")
            f.write(":80 {\n    respond 404\n}\n:443 {\n    respond 404\n}\n")
        logger.info(f"Created Caddyfile at {caddyfile}")

    def fetch_base_compose_file(self):
        """Fetch base docker-compose file."""
        logger.info(f"Fetching base compose file to {self.compose_file}...")
        subprocess.run(["curl", "--proto", "=https", "--tlsv1.2", "-sSf", BASE_COMPOSE_FILE_URL, "-o", str(self.compose_file)], check=True)

    def fetch_base_env_file(self):
        """Fetch base .env file."""
        logger.info(f"Fetching base .env file to {self.env_file}...")
        subprocess.run(["curl", "--proto", "=https", "--tlsv1.2", "-sSf", BASE_ENV_FILE_URL, "-o", str(self.env_file)], check=True)

    def update_env_file(self):
        """Update .env file with configuration."""
        logger.info(f"Updating {self.env_file}...")
        env_content = self.env_file.read_text()
        env_updates = {
            "CORE_IMAGE_TAG": self.core_image_tag,
            "PROXY_IMAGE_TAG": self.proxy_image_tag,
            "GATEWAY_IMAGE_TAG": self.gateway_image_tag,
            "DEFGUARD_AUTH_SECRET": self.generate_secret(),
            "DEFGUARD_YUBIBRIDGE_SECRET": self.generate_secret(),
            "DEFGUARD_GATEWAY_SECRET": self.generate_secret(),
            "DEFGUARD_SECRET_KEY": self.generate_secret(),
            "DEFGUARD_DB_PASSWORD": os.environ.get("DEFGUARD_DB_PASSWORD", self.generate_secret(PASSWORD_LENGTH)),
            "DEFGUARD_DEFAULT_ADMIN_PASSWORD": os.environ.get("DEFGUARD_DEFAULT_ADMIN_PASSWORD", self.generate_secret(PASSWORD_LENGTH)),
            "DEFGUARD_URL": self.config.defguard_url,
            "DEFGUARD_WEBAUTHN_RP_ID": self.config.domain
        }
        self.config.db_password = env_updates["DEFGUARD_DB_PASSWORD"]
        self.config.admin_password = env_updates["DEFGUARD_DEFAULT_ADMIN_PASSWORD"]
        if self.config.enable_enrollment:
            env_updates["DEFGUARD_ENROLLMENT_URL"] = self.config.enrollment_url

        for key, value in env_updates.items():
            pattern = f"^{key}=.*$"
            if re.search(pattern, env_content, re.MULTILINE):
                env_content = re.sub(pattern, f"{key}={value}", env_content, flags=re.MULTILINE)
            else:
                env_content += f"\n{key}={value}"

        self.env_file.write_text(env_content)
        if not self.config.use_https:
            env_content = env_content.replace("# [HTTP]", "")
            self.env_file.write_text(env_content)

    def enable_enrollment(self):
        """Enable enrollment proxy service."""
        logger.info("Enabling enrollment proxy service...")
        compose_content = self.compose_file.read_text().replace("# [ENROLLMENT]", "")
        self.compose_file.write_text(compose_content)
        env_content = self.env_file.read_text().replace("# [ENROLLMENT]", "")
        self.env_file.write_text(env_content)

    def enable_vpn_gateway(self):
        """Enable and configure VPN gateway."""
        logger.info("Enabling VPN gateway service...")
        compose_content = self.compose_file.read_text().replace("# [VPN]", "")
        self.compose_file.write_text(compose_content)
        env_content = self.env_file.read_text().replace("# [VPN]", "")
        self.env_file.write_text(env_content)

        logger.info(f"Pulling {self.image_type_name} gateway image...")
        subprocess.run(f"{self.compose_cmd} -f {self.compose_file} --env-file {self.env_file} pull gateway", shell=True, check=True)

        vpn_network = ".".join(self.config.vpn_ip.split("/")[:-1]) + ".0/" + self.config.vpn_ip.split("/")[-1]
        logger.info("Adding VPN to core & generating gateway token...")
        cmd = (f"{self.compose_cmd} -f {self.compose_file} --env-file {self.env_file} run core init-vpn-location "
               f"--name {self.config.vpn_name} --address {self.config.vpn_ip} --endpoint {self.config.vpn_gateway_ip} "
               f"--port {self.config.vpn_gateway_port} --allowed-ips {vpn_network}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("Failed to create VPN network")
        token = result.stdout.strip().split("\n")[-1]
        env_content = self.env_file.read_text()
        env_content = re.sub(r"^DEFGUARD_TOKEN=.*$", f"DEFGUARD_TOKEN={token}", env_content, flags=re.MULTILINE)
        self.env_file.write_text(env_content)

    def pull_images(self):
        """Pull container images with progress feedback."""
        logger.info(f"Pulling {self.image_type_name} {self.container_runtime} images...")
        with tqdm(total=3, desc="Pulling images") as pbar:
            subprocess.run(f"{self.compose_cmd} -f {self.compose_file} --env-file {self.env_file} pull", shell=True, check=True)
            pbar.update(3)

    def start_stack(self):
        """Start container Compose stack."""
        logger.info(f"Starting {self.container_runtime} Compose stack...")
        subprocess.run(f"{self.compose_cmd} -f {self.compose_file} --env-file {self.env_file} up -d", shell=True, check=True)

    def health_check(self):
        """Perform health check on container services."""
        logger.info(f"Performing health check on {self.container_runtime} services...")
        services = ["core", "proxy"]
        if self.config.enable_vpn:
            services.append("gateway")
        if self.config.enable_enrollment:
            services.append("enrollment")
        for service in services:
            result = subprocess.run(
                f"{self.compose_cmd} -f {self.compose_file} --env-file {self.env_file} ps -q {service}",
                shell=True, capture_output=True, text=True
            )
            if result.returncode != 0 or not result.stdout.strip():
                raise RuntimeError(f"Service {service} is not running")
            logger.info(f"Service {service} is running")

    def print_summary(self):
        """Print deployment summary."""
        logger.info(f"defguard setup finished successfully. {self.container_runtime.capitalize()} image version: {self.image_type_name}")
        logger.info(f"Web UI: {self.config.defguard_url}")
        if self.config.enable_enrollment:
            logger.info(f"Enrollment service: {self.config.enrollment_url}")
        logger.info("Default admin user:")
        logger.info(f"  Username: admin")
        logger.info(f"  Password: {self.config.admin_password}")
        logger.info(f"Database password: {self.config.db_password}")
        if self.config.enable_vpn:
            vpn_network = ".".join(self.config.vpn_ip.split("/")[:-1]) + ".0/" + self.config.vpn_ip.split("/")[-1]
            logger.info(f"VPN server public endpoint: {self.config.vpn_gateway_ip}:{self.config.vpn_gateway_port}")
            logger.info(f"VPN network: {vpn_network}")
            logger.info(f"Ensure firewall allows UDP traffic to port {self.config.vpn_gateway_port}")
        logger.info(f"{self.container_runtime.capitalize()} compose file: {self.compose_file}")
        logger.info(f"{self.container_runtime.capitalize()} compose environment: {self.env_file}")
        logger.info(f"Persistent data stored in: {self.config.volume_dir}")
        logger.info("Support us by starring on GitHub: https://github.com/defguard/defguard")

def load_config_from_file(file_path: str) -> DefguardConfig:
    """Load configuration from a YAML or JSON file."""
    config = DefguardConfig()
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file {file_path} not found")
    with open(file_path) as f:
        if file_path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    for key, value in data.items():
        setattr(config, key.replace("-", "_"), value)
    return config

def load_config_from_args() -> DefguardConfig:
    """Load configuration from command-line arguments."""
    parser = argparse.ArgumentParser(description="defguard deployment script")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode")
    parser.add_argument("--use-https", action="store_true", help="Configure reverse proxy to use HTTPS")
    parser.add_argument("--domain", help="Domain for defguard web UI")
    parser.add_argument("--enrollment-domain", help="Domain for enrollment service")
    parser.add_argument("--volume", default=VOLUME_DIR, help="Docker volumes directory")
    parser.add_argument("--vpn-name", help="VPN location name")
    parser.add_argument("--vpn-ip", help="VPN server address and subnet (e.g., 10.0.50.1/24)")
    parser.add_argument("--vpn-gateway-ip", help="VPN gateway external IP")
    parser.add_argument("--vpn-gateway-port", help="VPN gateway external port")
    parser.add_argument("--dev", action="store_true", help="Use development images")
    parser.add_argument("--pre-release", action="store_true", help="Use pre-release images")
    parser.add_argument("--config-file", help="Path to configuration file (YAML/JSON)")
    args = parser.parse_args()

    config = DefguardConfig()
    for key, value in vars(args).items():
        if value is not None:
            setattr(config, key.replace("-", "_"), value)
    if args.dev and args.pre_release:
        raise ValueError("Cannot set both --dev and --pre-release flags")
    return config

def load_config_from_env(config: DefguardConfig):
    """Load configuration from environment variables and .env file."""
    # Load .env file from current directory if it exists
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
        logger.info(f"Loaded .env file from {env_file}")

    env_mappings = {
        "DEFGUARD_DOMAIN": "domain",
        "DEFGUARD_ENROLLMENT_DOMAIN": "enrollment_domain",
        "DEFGUARD_USE_HTTPS": "use_https",
        "DEFGUARD_VOLUME_DIR": "volume_dir",
        "DEFGUARD_VPN_NAME": "vpn_name",
        "DEFGUARD_VPN_IP": "vpn_ip",
        "DEFGUARD_VPN_GATEWAY_IP": "vpn_gateway_ip",
        "DEFGUARD_VPN_GATEWAY_PORT": "vpn_gateway_port",
        "DEFGUARD_DEV": "dev",
        "DEFGUARD_PRE_RELEASE": "pre_release",
        "DEFGUARD_DB_PASSWORD": "db_password",
        "DEFGUARD_DEFAULT_ADMIN_PASSWORD": "admin_password"
    }
    for env_key, config_key in env_mappings.items():
        value = os.environ.get(env_key)
        if value:
            if config_key in ["use_https", "dev", "pre_release"]:
                setattr(config, config_key, value.lower() == "true")
            else:
                setattr(config, config_key, value)
    logger.info("Loaded configuration from environment variables")

def load_config_from_input(config: DefguardConfig):
    """Load configuration from user input."""
    if config.non_interactive:
        return
    logger.info("Please provide configuration values. Press enter to use defaults.")
    config.domain = input(f"Enter defguard domain [default: {config.domain or ''}]: ") or config.domain
    config.enrollment_domain = input(f"Enter enrollment domain [default: {config.enrollment_domain or ''}]: ") or config.enrollment_domain
    config.use_https = input(f"Use HTTPS [default: {config.use_https}]: ").lower() == "true" or config.use_https
    if input("Configure WireGuard VPN? [y/N]: ").lower() == "y":
        config.vpn_name = input(f"Enter VPN location name [default: {config.vpn_name or ''}]: ") or config.vpn_name
        config.vpn_ip = input(f"Enter VPN server address and subnet (e.g., 10.0.50.1/24) [default: {config.vpn_ip or ''}]: ") or config.vpn_ip
        config.vpn_gateway_ip = input(f"Enter VPN gateway public IP [default: {config.vpn_gateway_ip or ''}]: ") or config.vpn_gateway_ip
        config.vpn_gateway_port = input(f"Enter VPN gateway public port [default: {config.vpn_gateway_port or ''}]: ") or config.vpn_gateway_port

def main():
    """Main deployment function."""
    try:
        config = load_config_from_args()
        if config.config_file:
            config = load_config_from_file(config.config_file)
        load_config_from_env(config)
        load_config_from_input(config)
        config.validate()
        config.generate_urls()

        deployer = DefguardDeployer(config)
        deployer.check_environment()
        deployer.setup_docker_image_version()
        deployer.setup_keys()
        deployer.create_caddyfile()
        deployer.fetch_base_compose_file()
        deployer.fetch_base_env_file()
        deployer.update_env_file()
        if config.enable_enrollment:
            deployer.enable_enrollment()
        if config.enable_vpn:
            deployer.enable_vpn_gateway()
        deployer.pull_images()
        deployer.start_stack()
        deployer.health_check()
        deployer.print_summary()
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()