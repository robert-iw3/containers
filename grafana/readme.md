# Grafana/Loki Stack Deployment

## SSO deployment (`sso/`)

`sso/docker-compose.yml` runs Grafana behind traefik TLS with tinyauth
single sign-on. tinyauth is the policy enforcement point — local users by
default, or any OIDC provider via the `GENERIC_*` settings in
[`../ci/sso/tinyauth-oidc.env.example`](../ci/sso/tinyauth-oidc.env.example)
placed in `sso/tinyauth.env`. traefik copies the authenticated identity
into `Remote-User`, which Grafana's `auth.proxy` uses to sign the user in,
so one login reaches the dashboards. Callers presenting a bearer token skip
the interactive gate and are validated by Grafana directly.

```sh
cd uat && ./run-uat.sh          # TLS + SSO smoke test, build -> login
cd uat && ./run-uat.sh --down   # tear down
cd ansible && ansible-playbook -i inventory.ini deploy.yml   # deploy
```

The shared pattern is documented in [`../ci/sso/README.md`](../ci/sso/README.md).

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