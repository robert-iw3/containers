import os
import argparse
import ansible_runner
import requests
import yaml
from pathlib import Path

def validate_file(file_path):
    """Validate that a file exists and is valid YAML."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File {file_path} does not exist")
    try:
        with open(path, 'r') as f:
            yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}")
    return file_path

def validate_vault(vault_addr):
    """Validate Vault connectivity."""
    try:
        response = requests.get(f"{vault_addr}/v1/sys/health", timeout=5)
        if response.status_code not in [200, 429, 472, 473]:
            raise Exception(f"Vault unreachable: {response.status_code}")
    except Exception as e:
        print(f"Vault connectivity error: {e}")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description="Deploy Gitea stack using Ansible")
    parser.add_argument(
        "--platform",
        choices=["docker", "podman", "kubernetes"],
        required=True,
        help="Deployment platform: docker, podman, or kubernetes"
    )
    parser.add_argument(
        "--inventory",
        default="inventory",
        help="Path to Ansible inventory file (default: inventory)"
    )
    parser.add_argument(
        "--vault-addr",
        default="http://vault:8200",
        help="HashiCorp Vault address (default: http://vault:8200)"
    )
    parser.add_argument(
        "--vault-role-id",
        required=True,
        help="Vault AppRole role ID"
    )
    parser.add_argument(
        "--vault-secret-id",
        required=True,
        help="Vault AppRole secret ID"
    )
    parser.add_argument(
        "--backup-encryption-key",
        required=True,
        help="Key for encrypting PostgreSQL backups"
    )
    parser.add_argument(
        "--use-letsencrypt",
        action="store_true",
        help="Use Let's Encrypt for SSL certificates (default: self-signed)"
    )
    args = parser.parse_args()

    # Validate inventory file
    validate_file(args.inventory)

    # Set environment variables
    env_vars = {
        "VAULT_ADDR": args.vault_addr,
        "VAULT_ROLE_ID": args.vault_role_id,
        "VAULT_SECRET_ID": args.vault_secret_id,
        "BACKUP_ENCRYPTION_KEY": args.backup_encryption_key,
    }

    # Validate required environment variables
    required_env_vars = ["VAULT_ROLE_ID", "VAULT_SECRET_ID", "BACKUP_ENCRYPTION_KEY"]
    for var in required_env_vars:
        if not env_vars.get(var):
            print(f"Error: {var} environment variable is required")
            exit(1)

    # Validate Vault connectivity
    validate_vault(args.vault_addr)

    # Configure Ansible variables
    extra_vars = {
        "podman_enabled": args.platform == "podman",
        "kubernetes_enabled": args.platform == "kubernetes",
        "use_letsencrypt": args.use_letsencrypt,
    }

    # Run Ansible playbook
    try:
        result = ansible_runner.run(
            private_data_dir=".",
            playbook="deploy_gitea.yml",
            inventory=args.inventory,
            extravars=extra_vars,
            envvars=env_vars,
            verbosity=1,
        )
        if result.rc == 0:
            print("Deployment successful!")
            print(f"Access Gitea: https://{extra_vars.get('gitea_domain', 'gitea.example.com')}")
            print(f"Access Grafana: https://grafana.{extra_vars.get('gitea_domain', 'gitea.example.com')}")
            print(f"Access MinIO: https://minio.{extra_vars.get('gitea_domain', 'gitea.example.com')}")
            print(f"Access Prometheus: https://prometheus.{extra_vars.get('gitea_domain', 'gitea.example.com')}")
            print(f"Access Loki: https://loki.{extra_vars.get('gitea_domain', 'gitea.example.com')}")
            print(f"Access Traefik Dashboard: https://traefik.{extra_vars.get('gitea_domain', 'gitea.example.com')}/dashboard/")
            if not args.use_letsencrypt:
                print("Self-signed certificates used. Install ca.crt from ~/svc-gitea/gitea/certs/ to trust the CA.")
        else:
            print(f"Deployment failed: {result.status}")
            try:
                print(result.stdout.read().decode())
            except AttributeError:
                print("No stdout available from Ansible run")
    except Exception as e:
        print(f"Error running Ansible playbook: {e}")
        exit(1)

if __name__ == "__main__":
    main()