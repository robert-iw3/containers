# Artifactory Deployment Guide

## SSO deployment (`sso/`)

`sso/docker-compose.yml` runs Artifactory OSS behind traefik TLS with a
tinyauth single sign-on gate. Artifactory OSS has no HTTP header SSO (a
licensed feature), so tinyauth gates the web UI as a perimeter while
Artifactory keeps its own authentication. Registry (`/v2`, docker), REST
API (`/artifactory`) and access-token paths bypass the interactive gate — a
docker, Maven or CI client cannot complete a login redirect — and
authenticate with Artifactory access tokens.

tinyauth verifies local users by default, or any OIDC provider via
`sso/tinyauth.env` (see
[`../ci/sso/tinyauth-oidc.env.example`](../ci/sso/tinyauth-oidc.env.example)).

```sh
cd uat && ./run-uat.sh          # TLS + SSO smoke test, build -> login
cd uat && ./run-uat.sh --down   # tear down
cd ansible && ansible-playbook -i inventory.ini deploy.yml   # deploy
```

The shared pattern is documented in [`../ci/sso/README.md`](../ci/sso/README.md).

This guide provides instructions to deploy JFrog Artifactory using Docker, Podman, or Kubernetes.

## Prerequisites
- **Docker**, **Podman**, or **Kubernetes** installed.
- **Python 3** installed for running the deployment script.
- A working directory with sufficient disk space (~30GB recommended).

## Setup Instructions
1. **Clone the Repository or Copy Files**
   - Ensure you have the following files: `docker-compose.yml`, `artifactory-k8s.yml`, `deploy.py`, `setup.sh`, `.setup-env`.

2. **Run the Setup Script**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   This creates a `secrets/` directory with PostgreSQL credentials and initializes the `.setup-env` file.

3. **Edit .setup-env (Optional)**
   - Open `.setup-env` and update `ROOT_DATA_DIR` if you want a custom data directory (default: `$HOME/.jfrog/artifactory`).
   - Modify `JF_ROUTER_ENTRYPOINTS_EXTERNALPORT` if port 8082 is in use.

4. **Deploy Artifactory**
   Choose your platform and run:
   ```bash
   python3 deploy.py --platform docker
   ```
   or
   ```bash
   python3 deploy.py --platform podman
   ```
   or
   ```bash
   python3 deploy.py --platform kubernetes
   ```

5. **Access Artifactory**
   - Open a browser and navigate to `http://localhost:8082` (or the port specified in `JF_ROUTER_ENTRYPOINTS_EXTERNALPORT`).
   - Default login: `admin` / `password` (change immediately after login).

## Notes
- For Kubernetes, ensure your cluster is running and `kubectl` is configured.
- Secrets are stored in `secrets/` for Docker/Podman or in `artifactory-secrets` for Kubernetes.
- Ensure the `ROOT_DATA_DIR` has enough storage for Artifactory and Postgres data.
- For production, configure TLS certificates in Nginx and update the Postgres password in `secrets/postgres_password.txt` or the Kubernetes secret.

## Troubleshooting
- Check logs: `docker-compose logs` or `kubectl logs <pod-name>`.
- Verify services are running: `docker ps` or `kubectl get pods`.
- Ensure ports 8081, 8082, 8085, and 5432 are not in use.