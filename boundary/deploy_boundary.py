import os
import subprocess
import argparse
import yaml
import secrets
import string
from pathlib import Path

def generate_random_string(length=32):
    """Generate a random string for secrets."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def check_prerequisites(deployment_type):
    """Check if required tools are installed."""
    if deployment_type in ["docker", "podman"]:
        cmd = deployment_type
        try:
            subprocess.run([cmd, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            raise Exception(f"{cmd} is not installed or not accessible.")
    elif deployment_type == "kubernetes":
        try:
            subprocess.run(["kubectl", "version", "--client"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            raise Exception("kubectl is not installed or not accessible.")

def setup_environment():
    """Set up environment variables and create .env file if needed."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    if not env_file.exists():
        if env_example.exists():
            with env_example.open('r') as f:
                env_content = f.read()
            with env_file.open('w') as f:
                f.write(env_content)
        else:
            env_vars = {
                "POSTGRESQL_USERNAME": "boundary",
                "POSTGRESQL_PASSWORD": generate_random_string(),
                "POSTGRESQL_DATABASE": "boundary",
                "POSTGRESQL_REPLICATION_USER": "repl_user",
                "POSTGRESQL_REPLICATION_PASSWORD": generate_random_string(),
                "BOUNDARY_ROOT_KEY": generate_random_string(),
                "BOUNDARY_WORKER_AUTH_KEY": generate_random_string(),
                "BOUNDARY_RECOVERY_KEY": generate_random_string(),
            }
            with env_file.open('w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
    return {line.split("=", 1)[0]: line.split("=", 1)[1].strip() for line in env_file.read_text().splitlines() if "=" in line}

def deploy_docker_podman(deployment_type):
    """Deploy Boundary using Docker or Podman."""
    env_vars = setup_environment()
    cmd = [
        deployment_type, "compose", "-f", "docker-compose.yml", "up", "-d", "--build"
    ]
    subprocess.run(cmd, check=True, env={**os.environ, **env_vars})
    print(f"Boundary deployed successfully with {deployment_type}.")

def deploy_kubernetes():
    """Deploy Boundary to Kubernetes."""
    env_vars = setup_environment()
    secret_yaml = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "boundary-secrets", "namespace": "boundary"},
        "type": "Opaque",
        "stringData": {
            "postgresql-username": env_vars["POSTGRESQL_USERNAME"],
            "postgresql-password": env_vars["POSTGRESQL_PASSWORD"],
            "postgresql-database": env_vars["POSTGRESQL_DATABASE"],
            "postgresql-replication-user": env_vars["POSTGRESQL_REPLICATION_USER"],
            "postgresql-replication-password": env_vars["POSTGRESQL_REPLICATION_PASSWORD"],
            "boundary-root-key": env_vars["BOUNDARY_ROOT_KEY"],
            "boundary-worker-auth-key": env_vars["BOUNDARY_WORKER_AUTH_KEY"],
            "boundary-recovery-key": env_vars["BOUNDARY_RECOVERY_KEY"],
        }
    }
    with open("boundary-secrets.yaml", "w") as f:
        yaml.safe_dump(secret_yaml, f)

    subprocess.run(["kubectl", "apply", "-f", "boundary-secrets.yaml"], check=True)
    subprocess.run(["kubectl", "apply", "-f", "boundary-kubernetes.yaml"], check=True)
    print("Boundary deployed successfully to Kubernetes.")

def main():
    parser = argparse.ArgumentParser(description="Automate Boundary deployment.")
    parser.add_argument("--type", choices=["docker", "podman", "kubernetes"], required=True, help="Deployment type")
    args = parser.parse_args()

    check_prerequisites(args.type)
    if args.type in ["docker", "podman"]:
        deploy_docker_podman(args.type)
    else:
        deploy_kubernetes()

if __name__ == "__main__":
    main()