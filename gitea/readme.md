# Gitea Deployment

This project deploys a production-ready Gitea instance with PostgreSQL (via Patroni), PgBouncer, Traefik, MinIO, Prometheus, Grafana, and Loki for logging and monitoring. It supports deployment via Docker, Podman, or Kubernetes using Ansible for orchestration.

## Prerequisites

- **Ansible**: Version 2.9 or higher.
- **Podman** or **Docker**: For containerized deployment.
- **Kubernetes**: For Kubernetes deployment (e.g., via `kubectl`).
- **HashiCorp Vault**: For secret management (optional for Kubernetes).
- **Python 3**: For the deployment script.
- **Podman Socket**: Ensure `/run/user/<uid>/podman/podman.sock` is running for Podman deployments.
- **DNS/Hosts**: Configure DNS or `/etc/hosts` for `patroni-gitea.dev.io`, `loki.dev.io`, `minio.dev.io`, etc., for non-Kubernetes deployments.

## Directory Structure

```
.
├── templates/
│   ├── ca.conf.j2
│   ├── server.conf.j2
│   ├── docker-compose.yml.j2
│   ├── traefik.yml.j2
│   ├── prometheus.yml.j2
│   ├── modsecurity.conf.j2
│   ├── pgbouncer.ini.j2
│   ├── grafana-datasource.yml.j2
│   ├── backup.sh.j2
│   ├── vault_policy.hcl.j2
│   ├── gitea-k8s.yml.j2
├── deploy_gitea.yml
├── deploy_gitea.py
```

## Setup

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd gitea-deployment
   ```

2. **Prepare Vault Secrets**:
   - Store secrets in Vault at `secret/gitea` with keys: `postgresql_username`, `postgresql_password`, `postgresql_database`, `postgresql_replication_user`, `postgresql_replication_password`, `gitea_admin_user`, `gitea_admin_password`, `gitea_admin_email`, `gitea_domain`, `gitea_ssh_domain`, `gitea_root_url`, `gitea_ssh_port`, `minio_access_key`, `minio_secret_key`, `backup_encryption_key`.
   - Set environment variables `VAULT_ADDR`, `VAULT_ROLE_ID`, and `VAULT_SECRET_ID`.

3. **Prepare Certificates**:
   - For self-signed certificates, generate `ca.crt`, `server.crt`, and `server.key` using `ca.conf` and `server.conf`.
   - For Let's Encrypt, set `use_letsencrypt=true` in the deployment script.

4. **Configure DNS/Hosts**:
   - For non-Kubernetes deployments, ensure `/etc/hosts` or DNS resolves `patroni-gitea.dev.io`, `loki.dev.io`, `minio.dev.io`, etc.

## Deployment

Run the deployment script with the desired platform:

```bash
python3 deploy_gitea.py \
  --platform <docker|podman|kubernetes> \
  --inventory inventory \
  --vault-addr http://vault:8200 \
  --vault-role-id <role-id> \
  --vault-secret-id <secret-id> \
  --backup-encryption-key <encryption-key> \
  [--use-letsencrypt]
```

- **Docker/Podman**: Deploys using `docker-compose.yml` in `/home/svc-gitea/gitea-compose/`.
- **Kubernetes**: Applies `gitea-k8s.yml` to the cluster.
- **Inventory**: Specify the Ansible inventory file (default: `inventory`).

## Access

- **Gitea**: `https://<gitea_domain>/`
- **Grafana**: `https://grafana.<gitea_domain>/`
- **MinIO**: `https://minio.<gitea_domain>/`
- **Prometheus**: `https://prometheus.<gitea_domain>/`
- **Loki**: `https://loki.<gitea_domain>/`
- **Traefik Dashboard**: `https://traefik.<gitea_domain>/dashboard/` (user: `admin`, password: configured in Traefik config)

## Backup

- Backups are scheduled via a CronJob (Kubernetes) or cron (Docker/Podman) at 2 AM daily.
- PostgreSQL dumps are encrypted with GPG and stored in MinIO at `s3://gitea-backups/`.
- Logs are stored in `/tmp/backup.log` for debugging.

## Monitoring

- **Prometheus**: Scrapes metrics from Gitea, Patroni, PgBouncer, and Loki.
- **Grafana**: Visualizes metrics with a pre-configured dashboard using `grafana-datasource.yml`.
- **Loki**: Collects logs from Gitea and other services, with fallback to console logging if network logging fails.

## Security

- **Traefik**: Enforces HTTPS, rate limiting, and ModSecurity WAF using `traefik.yml` and `modsecurity.conf`.
- **Secrets**: Stored in Vault (Docker/Podman) or Kubernetes Secrets.
- **Certificates**: Supports Let's Encrypt or self-signed certificates (`ca.crt`, `server.crt`, `server.key`).
- **PgBouncer**: Connection pooling with MD5 authentication, configured via `pgbouncer.ini`.

## Troubleshooting

- **Logs**: Check `/tmp/backup.log` for backup issues or container logs for service issues.
- **Podman Socket**: Ensure `podman.socket` is running (`systemctl --user start podman.socket`).
- **DNS**: Verify resolution of internal hostnames using `getent hosts <hostname>`.
- **Vault**: Ensure Vault is accessible and secrets are correctly configured at `secret/gitea`.
- **SELinux**: For Podman, ensure correct SELinux labels are applied to volumes and sockets.