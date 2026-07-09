#!/usr/bin/env python3
import os
import subprocess
import logging
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_fixed
from deploy_keycloak import KeycloakDeployer, load_config
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class KeycloakDBRestorer(KeycloakDeployer):
    def __init__(self, config: Dict, namespace: str = "keycloak"):
        super().__init__(config, namespace)
        self.container_runtime = "podman" if os.path.exists("/usr/bin/podman") else "docker"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def list_backups_docker(self) -> List[str]:
        """List available backups in Docker/Podman environment."""
        logger.info("Listing available database backups")
        try:
            result = subprocess.run(
                [self.container_runtime, "container", "exec", "psql-backup", "ls", "/srv/keycloak-postgres/backups/"],
                capture_output=True, text=True, check=True
            )
            backups = result.stdout.strip().split("\n")
            return [b for b in backups if b.endswith(".gz")]
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def list_backups_kubernetes(self) -> List[str]:
        """List available backups in Kubernetes environment."""
        logger.info("Listing available database backups")
        try:
            result = subprocess.run(
                [self.kubectl, "exec", "-n", self.namespace, "deployment/psql-backup", "--", "ls", "/srv/keycloak-postgres/backups/"],
                capture_output=True, text=True, check=True
            )
            backups = result.stdout.strip().split("\n")
            return [b for b in backups if b.endswith(".gz")]
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def stop_keycloak_docker(self) -> bool:
        """Stop Keycloak container in Docker/Podman environment."""
        logger.info("Stopping Keycloak service")
        try:
            subprocess.run([self.container_runtime, "stop", "keycloak"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop Keycloak container: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def stop_keycloak_kubernetes(self) -> bool:
        """Scale down Keycloak deployment in Kubernetes."""
        logger.info("Scaling down Keycloak deployment")
        try:
            subprocess.run([self.kubectl, "scale", "-n", self.namespace, "deployment/keycloak", "--replicas=0"], check=True)
            subprocess.run([self.kubectl, "wait", "-n", self.namespace, "pod", "--for=delete", "--selector=app=keycloak", "--timeout=60s"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scale down Keycloak deployment: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def restore_database_docker(self, backup_file: str) -> bool:
        """Restore database in Docker/Podman environment."""
        logger.info(f"Restoring database from {backup_file}")
        try:
            restore_cmd = (
                f'PGPASSWORD="{self.config["POSTGRESQL_PASSWORD"]}" dropdb -h postgres-keycloak.io -p {self.config["DB_PORT"]} '
                f'{self.config["POSTGRESQL_DATABASE"]} -U {self.config["POSTGRESQL_USERNAME"]} && '
                f'PGPASSWORD="{self.config["POSTGRESQL_PASSWORD"]}" createdb -h postgres-keycloak.io -p {self.config["DB_PORT"]} '
                f'{self.config["POSTGRESQL_DATABASE"]} -U {self.config["POSTGRESQL_USERNAME"]} && '
                f'gunzip -c /srv/keycloak-postgres/backups/{backup_file} | '
                f'PGPASSWORD="{self.config["POSTGRESQL_PASSWORD"]}" psql -h postgres-keycloak.io -p {self.config["DB_PORT"]} '
                f'{self.config["POSTGRESQL_DATABASE"]} -U {self.config["POSTGRESQL_USERNAME"]}'
            )
            subprocess.run(
                [self.container_runtime, "exec", "psql-backup", "sh", "-c", restore_cmd],
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def restore_database_kubernetes(self, backup_file: str) -> bool:
        """Restore database in Kubernetes environment."""
        logger.info(f"Restoring database from {backup_file}")
        try:
            restore_cmd = (
                f'PGPASSWORD="{self.config["POSTGRESQL_PASSWORD"]}" dropdb -h postgres.keycloak.svc.cluster.local -p 5432 '
                f'{self.config["POSTGRESQL_DATABASE"]} -U {self.config["POSTGRESQL_USERNAME"]} && '
                f'PGPASSWORD="{self.config["POSTGRESQL_PASSWORD"]}" createdb -h postgres.keycloak.svc.cluster.local -p 5432 '
                f'{self.config["POSTGRESQL_DATABASE"]} -U {self.config["POSTGRESQL_USERNAME"]} && '
                f'gunzip -c /srv/keycloak-postgres/backups/{backup_file} | '
                f'PGPASSWORD="{self.config["POSTGRESQL_PASSWORD"]}" psql -h postgres.keycloak.svc.cluster.local -p 5432 '
                f'{self.config["POSTGRESQL_DATABASE"]} -U {self.config["POSTGRESQL_USERNAME"]}'
            )
            subprocess.run(
                [self.kubectl, "exec", "-n", self.namespace, "deployment/psql-backup", "--", "sh", "-c", restore_cmd],
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def start_keycloak_docker(self) -> bool:
        """Start Keycloak container in Docker/Podman environment."""
        logger.info("Starting Keycloak service")
        try:
            subprocess.run([self.container_runtime, "start", "keycloak"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Keycloak container: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def start_keycloak_kubernetes(self) -> bool:
        """Scale up Keycloak deployment in Kubernetes."""
        logger.info("Scaling up Keycloak deployment")
        try:
            subprocess.run([self.kubectl, "scale", "-n", self.namespace, "deployment/keycloak", "--replicas=1"], check=True)
            subprocess.run([self.kubectl, "wait", "-n", self.namespace, "pod", "--for=condition=ready", "--selector=app=keycloak", "--timeout=120s"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scale up Keycloak deployment: {e}")
            return False

    def validate_backup_file(self, backup_file: str, backups: List[str]) -> bool:
        """Validate the selected backup file."""
        if not backup_file.endswith(".gz"):
            logger.error("Backup file must have .gz extension")
            return False
        if backup_file not in backups:
            logger.error(f"Backup file {backup_file} not found")
            return False
        return True

    def restore(self, method: str = "docker", backup_file: Optional[str] = None) -> bool:
        """Restore Keycloak database from a backup."""
        logger.info(f"Starting database restore using {method} method")

        if not self.validate_config():
            return False
        if not self.check_requirements():
            return False

        backups = self.list_backups_kubernetes() if method == "kubernetes" else self.list_backups_docker()
        if not backups:
            logger.error("No backups found")
            return False

        logger.info("Available database backups:")
        for backup in backups:
            logger.info(backup)

        if not backup_file:
            backup_file = input("Copy and paste the backup name from the list above to restore database and press [ENTER]\nExample: keycloak-postgres-backup-YYYY-MM-DD_hh-mm.gz\n--> ")

        if not self.validate_backup_file(backup_file, backups):
            return False

        logger.info(f"{backup_file} was selected")

        if method == "kubernetes":
            if not self.stop_keycloak_kubernetes():
                return False
            if not self.restore_database_kubernetes(backup_file):
                return False
            if not self.start_keycloak_kubernetes():
                return False
        else:
            if not self.stop_keycloak_docker():
                return False
            if not self.restore_database_docker(backup_file):
                return False
            if not self.start_keycloak_docker():
                return False

        logger.info("Database recovery completed successfully")
        return True

def main():
    parser = argparse.ArgumentParser(description="Keycloak Database Restore Script")
    parser.add_argument("--method", choices=["kubernetes", "docker"], default="docker",
                        help="Restore method (kubernetes or docker)")
    parser.add_argument("--namespace", default="keycloak", help="Kubernetes namespace")
    parser.add_argument("--backup-file", help="Specific backup file to restore (e.g., keycloak-postgres-backup-YYYY-MM-DD_hh-mm.gz)")
    parser.add_argument("--postgresql-username", help="PostgreSQL username")
    parser.add_argument("--postgresql-password", help="PostgreSQL password")
    parser.add_argument("--postgresql-database", help="PostgreSQL database name")
    parser.add_argument("--db-port", default="5432", help="Database port")
    parser.add_argument("--letsencrypt-email", help="Let's Encrypt email for TLS certificates")

    args = parser.parse_args()

    config = load_config(args)  # Reuse load_config from deploy_keycloak.py
    restorer = KeycloakDBRestorer(config, args.namespace)

    try:
        if restorer.restore(args.method, args.backup_file):
            logger.info("Keycloak database restore completed successfully")
            return 0
        else:
            logger.error("Keycloak database restore failed")
            return 1
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())