# Grafana/Loki Stack Deployment

## Deploy the Stack

1. **Install Prerequisites**:
   - Install Docker or Podman.
   - For Kubernetes, install `kompose` and `kubectl`.
   - For Ansible, install `ansible`.
   - Install Python 3.8+ and dependencies:
     ```bash
     pip install -r requirements.txt
     ```

2. **Configure Environment**:
   - Copy the `.env` template:
     ```bash
     python deploy_stack.py --generate-env-template > .env
     ```
   - Edit `.env` with your values (e.g., LDAP, PostgreSQL, Wallarm, Traefik settings).

3. **Deploy the Stack**:
   - Deploy using Docker (or Podman, Kubernetes, Ansible):
     ```bash
     python deploy_stack.py --config config.yml --deploy-type docker
     ```
     Replace `docker` with `podman`, `kubernetes`, or `ansible` as needed.

4. **Manage Database**:
   - List backups:
     ```bash
     python deploy_stack.py --list-backups
     ```
   - Restore database:
     ```bash
     python deploy_stack.py --restore grafana-postgres-backup-YYYY-MM-DD_hh-mm.gz
     ```

## Access
- Grafana: `https://<GF_SERVER_DOMAIN>`
- Traefik Dashboard: `https://<TRAEFIK_DASHBOARD_DOMAIN>`
- Loki: `http://localhost:3100` (or configured port)
- Prometheus: `http://localhost:9090`