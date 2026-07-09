# Bitbucket Deployment

This project provides an automated, secure, and scalable deployment of Bitbucket (version 8.19) with Jira integration, monitoring, chaos engineering, and CI/CD pipelines using Docker, Podman, Kubernetes, and Ansible. The setup includes a custom Prometheus exporter for repository metrics, automated backups with `zstd`, Vault for secrets management, and multi-region support.

## Features
- **Deployment**: Bitbucket and PostgreSQL deployed via Docker/Podman or Kubernetes.
- **CI/CD**: Automated pipelines using GitLab CI and GitHub Actions with rollback capabilities.
- **Monitoring**: Prometheus, Grafana, and Alertmanager for metrics and alerts.
- **Custom Metrics**: Exporter for repository operations (push, pull, clone).
- **Security**: Vault for secrets, non-root containers, and Kubernetes network policies.
- **Resilience**: Chaos Mesh for chaos engineering and Pod Disruption Budgets (PDBs).
- **Scalability**: Multi-region DNS and Horizontal Pod Autoscaling (HPA).
- **Backups**: Automated PostgreSQL backups with `zstd` compression and restoration.

## Prerequisites
- **Docker/Podman**: For containerized deployment.
- **Kubernetes**: For scalable deployment (optional).
- **Ansible**: For infrastructure automation.
- **Python 3.9**: With dependencies listed in `requirements.txt`.
- **HashiCorp Vault**: For secrets management.
- **Prometheus/Grafana/Alertmanager**: For monitoring and alerting.
- **GitLab/GitHub**: For CI/CD pipelines.
- **Chaos Mesh**: For chaos engineering (optional).
- **ExternalDNS**: For multi-region DNS (optional).
- **zstd**: For backup compression.

## Directory Structure
- `deploy_bitbucket.py`: Python script for Docker deployment.
- `docker-compose.yml`: Docker Compose configuration for Bitbucket, PostgreSQL, and monitoring.
- `bitbucket-deployment.yml`: Kubernetes manifest for Bitbucket and custom exporter.
- `postgres-deployment.yml`: Kubernetes manifest for PostgreSQL with replication.
- `network-policy.yml`: Kubernetes network policy for access control.
- `multi-region.yml`: Ingress for multi-region DNS (`bitbucket.global.dev.io`).
- `chaos-test.yml`: Chaos Mesh experiments for resilience testing.
- `ansible-playbook.yml`: Ansible playbook for infrastructure setup.
- `test_deploy_bitbucket.py`: Unit tests for deployment script.
- `test_integration.py`: Integration tests for Bitbucket, PostgreSQL, and exporter.
- `restore_backup.sh`: Script for restoring PostgreSQL backups.
- `prometheus.yml`: Prometheus configuration for scraping metrics.
- `prometheus-alerts.yml`: Prometheus alert rules for monitoring.
- `grafana/provisioning/datasources/datasource.yml`: Grafana Prometheus datasource.
- `grafana/provisioning/dashboards/dashboard.yml`: Grafana dashboard provisioning.
- `grafana/dashboards/bitbucket.json`: Grafana dashboard for metrics visualization.
- `.gitlab-ci.yml`: GitLab CI pipeline for testing, deployment, and chaos testing.
- `.github/workflows/deploy.yml`: GitHub Actions pipeline for testing, deployment, and chaos testing.
- `.env`: Environment variables for configuration.
- `bitbucket-exporter.py`: Custom Prometheus exporter for repository metrics.
- `requirements.txt`: Python dependencies for all scripts.

## Setup Instructions

### 1. JMX Exporter for Bitbucket
1. Download the JMX Prometheus Java agent:
   ```bash
   wget https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar -P /opt/atlassian/bitbucket
   ```
2. Create `/opt/atlassian/bitbucket/prometheus.yml`:
   ```yaml
   rules:
     - pattern: ".*"
   ```

### 2. HashiCorp Vault Setup
1. Enable the database secrets engine:
   ```bash
   vault secrets enable database
   vault write database/config/bitbucket-postgres \
       plugin_name=postgresql-database-plugin \
       allowed_roles="bitbucket-role" \
       connection_url="postgresql://{{username}}:{{password}}@postgres-bitbucket.dev.io:5432/bitbucket" \
       username="bitbucket_user" \
       password="secure_password_123"
   vault write database/roles/bitbucket-role \
       db_name=bitbucket-postgres \
       creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';" \
       default_ttl="1h" \
       max_ttl="24h"
   ```
2. Store secrets in Vault:
   ```bash
   vault kv put secret/bitbucket \
       POSTGRESQL_PASSWORD=secure_password_123 \
       POSTGRESQL_REPLICATION_PASSWORD=replpass \
       JIRA_CLIENT_ID=<id> \
       JIRA_CLIENT_SECRET=<secret> \
       BITBUCKET_ADMIN_USER=admin \
       BITBUCKET_ADMIN_PASSWORD=admin_password \
       BITBUCKET_SUBNET=172.28.0.0/24 \
       BITBUCKET_GATEWAY=172.28.0.1 \
       POSTGRESQL_IPv4=172.28.0.2 \
       BACKUP_POSTGRESQL_IPv4=172.28.0.3 \
       BITBUCKET_IPv4=172.28.0.4 \
       PROMETHEUS_IPv4=172.28.0.5 \
       POSTGRES_EXPORTER_IPv4=172.28.0.6 \
       GRAFANA_IPv4=172.28.0.7 \
       ALERTMANAGER_IPv4=172.28.0.8 \
       BITBUCKET_EXPORTER_IPv4=172.28.0.9 \
       POSTGRESQL_USERNAME=bitbucket_user \
       POSTGRESQL_DATABASE=bitbucket \
       POSTGRESQL_REPLICATION_USER=repluser \
       BITBUCKET_JVM_MINIMUM_MEMORY=1024m \
       BITBUCKET_JVM_MAXIMUM_MEMORY=4096m \
       BITBUCKET_HOSTNAME=bitbucket.dev.io \
       BITBUCKET_URL=https://bitbucket.dev.io \
       JIRA_URL=https://jira.dev.io
   ```

### 3. Environment Variables
Edit `.env` with your configuration or rely on Vault for secrets. Example:
```plaintext
POSTGRESQL_PASSWORD=secure_password_123
POSTGRESQL_REPLICATION_PASSWORD=replpass
BITBUCKET_ADMIN_USER=admin
BITBUCKET_ADMIN_PASSWORD=admin_password
BITBUCKET_IPv4=172.28.0.4
BITBUCKET_EXPORTER_IPv4=172.28.0.9
```

### 4. Ansible Deployment
1. Configure Ansible inventory (`inventory.yml`):
   ```yaml
   bitbucket_nodes:
     hosts:
       docker_host:
         ansible_host: <docker_host_ip>
         ansible_user: <user>
         ansible_ssh_private_key_file: <path_to_key>
   k8s_nodes:
     hosts:
       k8s_master:
         ansible_host: <k8s_master_ip>
         ansible_user: <user>
         ansible_ssh_private_key_file: <path_to_key>
   ```
2. Run the Ansible playbook:
   ```bash
   ansible-playbook ansible-playbook.yml -i inventory.yml
   ```

### 5. CI/CD Pipelines
- **GitLab CI**: Configure `.gitlab-ci.yml` with secrets (`DOCKER_USERNAME`, `DOCKER_PASSWORD`, `VAULT_ADDR`, `VAULT_TOKEN`, `KUBE_CONFIG`, `BITBUCKET_IPv4`).
- **GitHub Actions**: Configure `.github/workflows/deploy.yml` with the same secrets.
- Both pipelines run tests, deploy to Docker/Kubernetes, validate backups, apply chaos tests, and handle rollbacks.

### 6. Monitoring Setup
1. Access Grafana at `http://<GRAFANA_IPv4>:3000` (default: `172.28.0.7:3000`).
2. View the "Bitbucket Dashboard" for JVM, PostgreSQL, HTTP, backup, and repository metrics.
3. Prometheus alerts are configured in `prometheus-alerts.yml` for high memory, connections, backup failures, and repository activity.

### 7. Chaos Engineering
- Apply `chaos-test.yml` for pod failure and network delay experiments:
  ```bash
  kubectl apply -f chaos-test.yml
  ```
- CI/CD pipelines automatically run chaos tests post-deployment to validate resilience.

### 8. Backup and Restore
- Backups are stored in `/srv/bitbucket-postgres/backups` with `zstd` compression.
- Restore a backup:
  ```bash
  ./restore_backup.sh bitbucket-postgres-backup-<timestamp>.sql.zst
  ```

## Deployment
- **Docker/Podman**:
  ```bash
  python3 deploy_bitbucket.py
  ```
- **Kubernetes**:
  ```bash
  kubectl apply -f bitbucket-deployment.yml -f postgres-deployment.yml -f network-policy.yml -f multi-region.yml
  ```

## Testing
- Run unit tests:
  ```bash
  python -m unittest test_deploy_bitbucket.py
  ```
- Run integration tests:
  ```bash
  python -m unittest test_integration.py
  ```

## Troubleshooting
- **Bitbucket not starting**: Check logs (`docker logs bitbucket` or `kubectl logs -n bitbucket <pod>`).
- **PostgreSQL connection issues**: Verify `POSTGRESQL_USERNAME`, `POSTGRESQL_PASSWORD`, and `JDBC_URL`.
- **Exporter metrics missing**: Ensure `bitbucket-exporter` is running (`http://172.28.0.9:8000/metrics`).
- **Vault errors**: Confirm `VAULT_ADDR` and `VAULT_TOKEN` are set correctly.
- **Chaos test failures**: Review Chaos Mesh logs (`kubectl -n bitbucket get chaosmesh`).

## Security Considerations
- Use Vault for secrets in production.
- Run containers as non-root users (`securityContext` in Kubernetes, `security_opt` in Docker).
- Restrict network access with `network-policy.yml`.
- Rotate Vault secrets regularly.

## Monitoring and Alerts
- Grafana dashboard (`bitbucket.json`) displays:
  - JVM memory usage
  - PostgreSQL connections
  - Backup status
  - HTTP request rates and latency
  - Repository operations (push, pull, clone)
- Alerts (`prometheus-alerts.yml`) notify on:
  - High JVM memory (>80%)
  - High PostgreSQL connections (>50)
  - Backup failures
  - High repository push rates (>100/min)
  - Exporter downtime
