import os
import subprocess
import uuid
import secrets
import argparse
import yaml
from pathlib import Path
from typing import Dict, Optional

def generate_secret(length: int = 50) -> str:
    """Generate a secure random secret."""
    return secrets.token_urlsafe(length)[:min(length, 99)]  # Respect PostgreSQL limit

def validate_env(env: Dict[str, str]) -> bool:
    """Validate required environment variables."""
    required = [
        "AUTHENTIK_SUBNET", "AUTHENTIK_GATEWAY", "POSTGRESQL_IPv4", "BACKUP_POSTGRESQL_IPv4",
        "REDIS_IPv4", "SERVER_IPv4", "WORKER_IPv4", "SOCKETPROXY_IPv4",
        "POSTGRESQL_USERNAME", "POSTGRESQL_PASSWORD", "POSTGRESQL_DATABASE",
        "POSTGRESQL_REPLICATION_USER", "POSTGRESQL_REPLICATION_PASSWORD",
        "AUTHENTIK_SECRET_KEY"
    ]
    missing = [var for var in required if not env.get(var)]
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        return False
    return True

def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """Load environment variables from a .env file."""
    env = {}
    if Path(env_file).exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    env[key] = value
    return env

def generate_env_file(env_file: str = ".env"):
    """Generate a .env file with secure defaults."""
    env = {
        "AUTHENTIK_SUBNET": "172.20.0.0/16",
        "AUTHENTIK_GATEWAY": "172.20.0.1",
        "POSTGRESQL_IPv4": "172.20.0.2",
        "BACKUP_POSTGRESQL_IPv4": "172.20.0.3",
        "REDIS_IPv4": "172.20.0.4",
        "SERVER_IPv4": "172.20.0.5",
        "WORKER_IPv4": "172.20.0.6",
        "SOCKETPROXY_IPv4": "172.20.0.7",
        "POSTGRESQL_USERNAME": "authentik",
        "POSTGRESQL_PASSWORD": generate_secret(40),
        "POSTGRESQL_DATABASE": "authentik",
        "POSTGRESQL_REPLICATION_USER": "repl_user",
        "POSTGRESQL_REPLICATION_PASSWORD": generate_secret(40),
        "AUTHENTIK_SECRET_KEY": generate_secret(50),
        "AUTHENTIK_EMAIL__HOST": "smtp.example.com",
        "AUTHENTIK_EMAIL__PORT": "587",
        "AUTHENTIK_EMAIL__USERNAME": "",
        "AUTHENTIK_EMAIL__PASSWORD": "",
        "AUTHENTIK_EMAIL__FROM": "authentik@example.com",
        "COMPOSE_PORT_HTTP": "9000",
        "COMPOSE_PORT_HTTPS": "9443",
        "SOCKET_PATH": "/var/run/docker.sock"
    }
    with open(env_file, "w") as f:
        f.write("# Authentik Deployment Environment Variables\n")
        for key, value in env.items():
            f.write(f"{key}={value}\n")
    print(f"Generated {env_file} with secure defaults.")
    return env

def deploy_docker_compose(compose_file: str, env_file: str):
    """Deploy using Docker Compose or Podman."""
    env = load_env_file(env_file)
    if not validate_env(env):
        raise ValueError("Environment validation failed.")
    cmd = ["docker-compose", "-f", compose_file, "up", "-d"]
    if os.getenv("USE_PODMAN"):
        cmd = ["podman-compose", "-f", compose_file, "up", "-d"]
    subprocess.run(cmd, check=True)
    print(f"Deployed Authentik using {compose_file}")

def deploy_kubernetes(manifest_file: str, env_file: str):
    """Deploy using Kubernetes."""
    env = load_env_file(env_file)
    if not validate_env(env):
        raise ValueError("Environment validation failed.")
    subprocess.run(["kubectl", "apply", "-f", manifest_file], check=True)
    print(f"Deployed Authentik to Kubernetes using {manifest_file}")

def main():
    parser = argparse.ArgumentParser(description="Deploy Authentik with Docker, Podman, or Kubernetes.")
    parser.add_argument("--generate-env", action="store_true", help="Generate a new .env file.")
    parser.add_argument("--deploy", choices=["docker", "podman", "kubernetes"], required=True, help="Deployment method.")
    parser.add_argument("--compose-file", default="prod-docker-compose.yml", help="Docker Compose file path.")
    parser.add_argument("--k8s-manifest", default="authentik-k8s.yml", help="Kubernetes manifest file path.")
    parser.add_argument("--env-file", default=".env", help="Environment file path.")
    args = parser.parse_args()

    if args.generate_env:
        generate_env_file(args.env_file)

    if args.deploy in ["docker", "podman"]:
        os.environ["USE_PODMAN"] = "1" if args.deploy == "podman" else ""
        deploy_docker_compose(args.compose_file, args.env_file)
    elif args.deploy == "kubernetes":
        deploy_kubernetes(args.k8s_manifest, args.env_file)

if __name__ == "__main__":
    main()