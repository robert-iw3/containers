import os
import subprocess
import argparse
import json
import yaml
from datetime import datetime
import getpass
import sys
import logging
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
ENV_FILE = '.env'
ENV_TEMPLATE_FILE = 'env_template.txt'
OPENAPI_FILE = 'jira-api-openapi.json'
OPENAPI_TEMPLATE_FILE = 'jira-api-openapi_template.json'
COMPOSE_FILE = 'docker-compose.yml'
PROMETHEUS_CONFIG_FILE = 'prometheus.yml'
K8S_MANIFEST_DIR = 'k8s_manifests'
ANSIBLE_PLAYBOOK_DIR = 'ansible_playbooks'
K8S_DEPLOYMENT_TEMPLATE_FILE = 'k8s_deployment_template.yaml'
ANSIBLE_PLAYBOOK_TEMPLATE_FILE = 'ansible_playbook_template.yaml'

def load_template(file_path: str) -> str:
    """Load template from file"""
    if not os.path.exists(file_path):
        logger.error(f"Template file {file_path} not found.")
        sys.exit(1)
    with open(file_path, 'r') as f:
        return f.read()

def load_env() -> Dict[str, str]:
    """Manually load .env file into a dictionary"""
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env[key.strip()] = value.strip()
    return env

def generate_env_file():
    """Generate or update .env with secure prompts"""
    env_template = load_template(ENV_TEMPLATE_FILE)
    if not os.path.exists(ENV_FILE):
        postgres_password = getpass.getpass("Enter PostgreSQL password: ")
        repl_password = getpass.getpass("Enter PostgreSQL replication password: ")
        wallarm_token = getpass.getpass("Enter Wallarm API token: ")
        grafana_password = getpass.getpass("Enter Grafana admin password: ")

        env_content = env_template.format(
            postgres_password=postgres_password,
            repl_password=repl_password,
            wallarm_token=wallarm_token,
            grafana_password=grafana_password
        )
        with open(ENV_FILE, 'w') as f:
            f.write(env_content)
        logger.info(f"Generated {ENV_FILE}")
    else:
        logger.info(f"{ENV_FILE} already exists. Skipping generation.")

def generate_openapi_spec():
    """Generate simple OpenAPI JSON for Wallarm from template"""
    if not os.path.exists(OPENAPI_TEMPLATE_FILE):
        logger.error(f"OpenAPI template {OPENAPI_TEMPLATE_FILE} not found.")
        sys.exit(1)
    with open(OPENAPI_TEMPLATE_FILE, 'r') as f:
        spec = json.load(f)
    with open(OPENAPI_FILE, 'w') as f:
        json.dump(spec, f, indent=4)
    logger.info(f"Generated {OPENAPI_FILE}")

def enhance_compose_files():
    """Copy or generate enhanced compose file"""
    enhanced_compose = load_template('enhanced_compose_template.yaml')
    with open(COMPOSE_FILE, 'w') as f:
        f.write(enhanced_compose)
    logger.info(f"Generated {COMPOSE_FILE}")

    prometheus_yml = load_template('prometheus_template.yaml')
    with open(PROMETHEUS_CONFIG_FILE, 'w') as f:
        f.write(prometheus_yml)
    logger.info(f"Generated {PROMETHEUS_CONFIG_FILE}")

def generate_k8s_manifests():
    """Generate basic K8s manifests using template"""
    k8s_template = load_template(K8S_DEPLOYMENT_TEMPLATE_FILE)
    os.makedirs(K8S_MANIFEST_DIR, exist_ok=True)
    services = ['postgresql', 'jira', 'wallarm-node', 'backups', 'traefik', 'prometheus', 'grafana']
    for service in services:
        manifest = k8s_template.format(service_name=service, image=f"placeholder/{service}:latest")
        with open(f"{K8S_MANIFEST_DIR}/{service}-deployment.yaml", 'w') as f:
            f.write(manifest)
    logger.info(f"Generated K8s manifests in {K8S_MANIFEST_DIR}")

def generate_ansible_playbooks():
    """Generate basic Ansible playbooks using template"""
    ansible_template = load_template(ANSIBLE_PLAYBOOK_TEMPLATE_FILE)
    os.makedirs(ANSIBLE_PLAYBOOK_DIR, exist_ok=True)
    playbook = ansible_template.format(compose_file=COMPOSE_FILE)
    with open(f"{ANSIBLE_PLAYBOOK_DIR}/deploy_jira.yml", 'w') as f:
        f.write(playbook)
    logger.info(f"Generated Ansible playbooks in {ANSIBLE_PLAYBOOK_DIR}")

def run_command(cmd: List[str], capture_output: bool = False) -> Optional[str]:
    """Run shell command with error handling"""
    try:
        result = subprocess.run(cmd, check=True, capture_output=capture_output, text=True)
        return result.stdout if capture_output else None
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

def list_backups(container: str, path: str) -> List[str]:
    """List backups in container"""
    cmd = ["docker", "exec", container, "ls", path]
    output = run_command(cmd, capture_output=True)
    return output.strip().split('\n') if output else []

def restore_application_data():
    """Improved Python version of application data restore script"""
    env_dict = load_env()
    jira_container = run_command(["docker", "ps", "-aqf", "name=jira"], capture_output=True).strip()
    backups_container = run_command(["docker", "ps", "-aqf", "name=backups-jira"], capture_output=True).strip()

    if not jira_container or not backups_container:
        logger.error("Containers not found.")
        return

    backups = list_backups(backups_container, "/backups/app")
    print("Available application data backups:")
    for b in backups:
        print(b)

    selected = input("Enter backup name to restore: ").strip()
    if selected not in backups:
        logger.error("Invalid backup selected.")
        return

    logger.info(f"Selected: {selected}")

    logger.info("Stopping Jira service...")
    run_command(["docker", "stop", jira_container])

    logger.info("Restoring application data...")
    restore_cmd = f"rm -rf /var/atlassian/application-data/jira/* && tar -zxpf /backups/app/{selected} -C /"
    run_command(["docker", "exec", backups_container, "sh", "-c", restore_cmd])

    logger.info("Starting Jira service...")
    run_command(["docker", "start", jira_container])

    logger.info("Application data restore completed.")

def restore_database():
    """Improved Python version of database restore script"""
    env_dict = load_env()
    jira_container = run_command(["docker", "ps", "-aqf", "name=jira"], capture_output=True).strip()
    backups_container = run_command(["docker", "ps", "-aqf", "name=backups-jira"], capture_output=True).strip()

    if not jira_container or not backups_container:
        logger.error("Containers not found.")
        return

    backups = list_backups(backups_container, "/backups/db")
    print("Available database backups:")
    for b in backups:
        print(b)

    selected = input("Enter backup name to restore: ").strip()
    if selected not in backups:
        logger.error("Invalid backup selected.")
        return

    logger.info(f"Selected: {selected}")

    logger.info("Stopping Jira service...")
    run_command(["docker", "stop", jira_container])

    logger.info("Restoring database...")
    pg_password = env_dict.get('POSTGRESQL_PASSWORD', '')
    username = env_dict.get('POSTGRESQL_USERNAME', 'jira_user')
    database = env_dict.get('POSTGRESQL_DATABASE', 'jira_db')

    drop_cmd = f"dropdb -h postgres-jira.dev -p 5432 -U {username} {database}"
    create_cmd = f"createdb -h postgres-jira.dev -p 5432 -U {username} {database}"
    restore_cmd = f"gunzip -c /backups/db/{selected} | psql -h postgres-jira.dev -p 5432 -U {username} {database}"

    run_command(["docker", "exec", "-e", f"PGPASSWORD={pg_password}", backups_container, "sh", "-c", drop_cmd])
    run_command(["docker", "exec", "-e", f"PGPASSWORD={pg_password}", backups_container, "sh", "-c", create_cmd])
    run_command(["docker", "exec", "-e", f"PGPASSWORD={pg_password}", backups_container, "sh", "-c", restore_cmd])

    logger.info("Starting Jira service...")
    run_command(["docker", "start", jira_container])

    logger.info("Database restore completed.")

def deploy_docker_podman(engine: str):
    """Deploy using Docker or Podman Compose"""
    compose_cmd = "docker-compose" if engine == "docker" else "podman-compose"
    run_command([compose_cmd, "-f", COMPOSE_FILE, "up", "-d"])
    logger.info(f"Deployed with {engine}")

def deploy_kubernetes():
    """Deploy to Kubernetes"""
    run_command(["kubectl", "apply", "-f", K8S_MANIFEST_DIR])
    logger.info("Deployed to Kubernetes")

def deploy_ansible():
    """Deploy using Ansible"""
    run_command(["ansible-playbook", f"{ANSIBLE_PLAYBOOK_DIR}/deploy_jira.yml"])
    logger.info("Deployed with Ansible")

def update_prometheus_config(additional_targets: List[str]):
    """Update Prometheus config with additional monitoring targets"""
    with open(PROMETHEUS_CONFIG_FILE, 'a') as f:
        for target in additional_targets:
            job_name, port = target.split(':')
            f.write(f"  - job_name: '{job_name}'\n    static_configs:\n      - targets: ['{job_name}:{port}']\n")
    logger.info("Updated Prometheus config with additional apps.")

def main():
    parser = argparse.ArgumentParser(description="Automated Jira Deployment")
    parser.add_argument("deployment_type", choices=["docker", "podman", "kubernetes", "ansible"], help="Deployment method")
    parser.add_argument("--restore-app", action="store_true", help="Restore application data")
    parser.add_argument("--restore-db", action="store_true", help="Restore database")
    parser.add_argument("--configure-monitoring", nargs="*", help="Additional app targets for monitoring (e.g., app1:port app2:port)")

    args = parser.parse_args()

    # Generate necessary files if not exist
    generate_env_file()
    generate_openapi_spec()
    enhance_compose_files()
    generate_k8s_manifests()
    generate_ansible_playbooks()

    # Handle monitoring configuration
    if args.configure_monitoring:
        update_prometheus_config(args.configure_monitoring)

    # Restore if requested
    if args.restore_app:
        restore_application_data()
    if args.restore_db:
        restore_database()

    # Deploy
    if args.deployment_type in ["docker", "podman"]:
        deploy_docker_podman(args.deployment_type)
    elif args.deployment_type == "kubernetes":
        deploy_kubernetes()
    elif args.deployment_type == "ansible":
        deploy_ansible()

if __name__ == "__main__":
    main()