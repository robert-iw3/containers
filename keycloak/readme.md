## Keycloak

<p align="center">
  <img src="https://developers.redhat.com/sites/default/files/styles/article_feature/public/blog/2020/11/2020_Authentication_Author_Keycloak_Featured_Article__B-copy-2.png?itok=geYdEfXu" width="400" />
</p>

## Keycloak Deployment

This project deploys Keycloak with PostgreSQL and Traefik for identity management, supporting Kubernetes, Docker/Podman, and Ansible.

## Prerequisites
- Install `kubectl`, `podman`, `podman-compose`, `ansible`, `python3`, `python3-tenacity`, and `openssl`.
- Ensure Docker or Podman is running.
- For Kubernetes, ensure a cluster is accessible and cert-manager is installed.

## Deployment Steps

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd keycloak
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your credentials, domains and a valid Let's Encrypt email.
   The compose stack runs Keycloak 26 (Quarkus) with modern `KC_*`
   configuration: TLS terminates at traefik, Keycloak serves HTTP on an
   internal network with `KC_PROXY_HEADERS=xforwarded`, and postgres is
   reachable only from the internal `keycloak-backend` network. The
   `KEYCLOAK_USER`/`KEYCLOAK_PASSWORD` values bootstrap the initial admin
   (`KC_BOOTSTRAP_ADMIN_*`) — rotate them after first login.

   **Smoke test / UAT** (self-contained, no DNS needed):
   ```bash
   ./uat/run-uat.sh        # TLS Keycloak on https://localhost:8543 + mock OIDC app
   ./uat/run-uat.sh --down # tear down
   ```
   The UAT generates a local CA, serves Keycloak over HTTPS (management
   port included), bootstraps a `uat` realm + demo user + confidential
   client via `kcadm`, then runs a **mock relying application**
   (oauth2-proxy in front of a `whoami` upstream) that performs the full
   OIDC authorization-code flow against Keycloak — demonstrating exactly
   how an application integrates with Keycloak as its IdP. The script
   prints both the admin console and mock-app URLs with credentials.

3. **Deploy**
   - **Kubernetes**:
     ```bash
     python3 deploy_keycloak.py --method kubernetes --letsencrypt-email your.email@example.com
     ```
   - **Docker/Podman**:
     ```bash
     python3 deploy_keycloak.py --method docker --letsencrypt-email your.email@example.com
     ```
   - **Ansible**:
     ```bash
     python3 deploy_keycloak.py --method ansible --letsencrypt-email your.email@example.com
     ```

4. **Restore Database (Optional)**
   List and restore a database backup:
   ```bash
   python3 restore_keycloak_db.py --method <kubernetes|docker> --letsencrypt-email your.email@example.com
   ```
   Follow prompts to select a backup file, or specify one:
   ```bash
   python3 restore_keycloak_db.py --method <kubernetes|docker> --backup-file keycloak-postgres-backup-YYYY-MM-DD_hh-mm.gz
   ```

5. **Access Keycloak**
   - URL: `https://keycloak.io:8443`
   - Admin Console: `https://keycloak.io:8443/admin`
   - Traefik Dashboard: `https://traefik.io`
   - Use credentials from `.env`.

6. **Verify Deployment**
   ```bash
   kubectl get pods,svc,ingressroute -n keycloak  # For Kubernetes
   podman ps  # For Docker/Podman
   ```

## Notes
- Replace `keycloak.io` and `traefik.io` with your domain in production.
- Generate a secure `TRAEFIK_AUTH_HASHED_PASSWORD` with `openssl passwd -6`.
- Monitor logs with `kubectl logs` or `podman logs`.
- Backups are stored in `keycloak-postgres-backups` volume, kept for 7 days.
## Deploy with Ansible

Each stack ships an Ansible deploy playbook (`ansible/deploy.yml`) that
brings the stack up via podman-compose:

```bash
cd keycloak/ansible
ansible-playbook -i inventory.ini deploy.yml
```
It seeds `.env` from `.env.example` on first run — fill in secrets first.
Validate playbook syntax with ansible-lint (run from a container, no host
install needed) from the repo root:

```bash
ci/ansible-lint.sh
```
