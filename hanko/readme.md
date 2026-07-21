# Hanko Authentication Service Deployment

This repository provides an optimized deployment setup for the Hanko Authentication Service, implementing zero trust security principles and automated deployment using Docker, Kubernetes, and Ansible. The setup includes TLS certificate management, Vault secret integration, and comprehensive monitoring.

## Quick start (compose)

```bash
cp .env.example .env       # dev defaults; change passwords for real deployments
./generate-tls.sh          # self-signed certs into ./tls (SANs cover service names)
podman-compose up -d postgresql
podman-compose up -d hanko-migrate hanko backups
podman-compose --profile dev up -d elements mailslurper   # dev-only extras
```

The compose stack uses the upstream `ghcr.io/teamhanko/hanko:v2.7.0`
image by default; set `HANKO_IMAGE`/`HANKO_TAG` (or build via
`backend/backend.Dockerfile`) to override. `config.yml` carries local
development defaults — its database credentials must match `.env`, and
both must be replaced for any non-local deployment. postgres runs TLS
with certs copied to a private path at startup and publishes no host
ports; the admin API (8001) binds to localhost only.

## Smoke test / UAT

```bash
./uat/run-uat.sh        # TLS hanko API + login page + mailslurper
./uat/run-uat.sh --down # tear down
```
The UAT is TLS end to end: a local CA, PostgreSQL with TLS, the hanko
API fronted by an nginx TLS terminator on `https://localhost:8000`
(hanko has no native TLS), and a TLS-served hanko-elements login page on
`https://localhost:8888` that, after login, calls the backend `/me`
endpoint — the same call a relying application makes — to prove the
integration. Passcode e-mails land in mailslurper (`http://localhost:8086`).

## Prerequisites

- Docker >= 24.0.0 or Podman >= 4.4.0
- Kubernetes cluster (tested with k8s >= 1.28)
- Ansible >= 2.14
- Python >= 3.10
- Helm >= 3.12
- kubectl configured for your cluster
- Access to a container registry
- Vault or similar secret management system
- cert-manager >= 1.15 for production TLS (optional for local development)

## Architecture Overview

The deployment includes:
- Backend service (Go-based API)
- Frontend elements (Nginx-served web components)
- PostgreSQL database with automated backups
- MailSlurper for email testing
- Vault for secret management
- Kubernetes for orchestration
- Ansible for automated deployment
- cert-manager for TLS certificates

## Security Features

- Zero Trust with mTLS and network policies
- Secret management with Vault
- Pod Security Standards (restricted)
- Network policies for least privilege
- Non-root containers with seccomp profiles
- Resource limits and reservations
- Secure cookie handling (HttpOnly, SameSite)
- CORS restrictions
- Encrypted communications with TLS
- Content Security Policy and HSTS headers

## Setup Instructions

1. **Clone the Repository**
```bash
# clone this repo
cd hanko
```

2. **Configure Environment Variables**
Create a `.env` file:
```bash
POSTGRESQL_USERNAME=hanko_user
POSTGRESQL_PASSWORD=secure_password
POSTGRESQL_DATABASE=hanko
POSTGRESQL_REPLICATION_USER=repl_user
POSTGRESQL_REPLICATION_PASSWORD=repl_secure_password
SMTP_AUTH_USER=smtp_user
SMTP_AUTH_PASSWORD=smtp_secure_password
VAULT_ADDR=https://vault.your-domain.com
VAULT_TOKEN=your-vault-token
CONTAINER_REGISTRY=your.registry.com
```

3. **Initialize Vault Secrets**
```bash
vault kv put secret/hanko \
  db_username="$POSTGRESQL_USERNAME" \
  db_password="$POSTGRESQL_PASSWORD" \
  repl_user="$POSTGRESQL_REPLICATION_USER" \
  repl_password="$POSTGRESQL_REPLICATION_PASSWORD" \
  smtp_user="$SMTP_AUTH_USER" \
  smtp_password="$SMTP_AUTH_PASSWORD" \
  jwt_secret="$(openssl rand -base64 32)"
```

4. **Generate TLS Certificates**
   - **For Local Development**:
     ```bash
     chmod +x generate-tls.sh
     ./generate-tls.sh
     ```
     This creates self-signed certificates in the `tls` directory and stores them in a Kubernetes secret (`hanko-tls`).
   - **For Production**:
     Install cert-manager:
     ```bash
     kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.3/cert-manager.yaml
     ```
     Apply the Let's Encrypt issuer:
     ```bash
     kubectl apply -f k8s/cert-manager-issuer.yml
     ```
     Update `helm/hanko/values.yaml` with your domain (`hanko.your-domain.com`).

5. **Install Dependencies**
```bash
pip install -r requirements.txt
ansible-galaxy install -r ansible/requirements.yml
```

6. **Deploy with Ansible**
```bash
ansible-playbook ansible/deploy.yml -i ansible/inventory.yml
```

7. **Alternative Deployment with Python Script**
Build and push images, then apply Kubernetes manifests:
```bash
python deploy.py --namespace hanko --registry $CONTAINER_REGISTRY
```

8. **Verify Deployment**
Check pod status:
```bash
kubectl get pods -n hanko
```
Test endpoints:
- API: `curl -k https://localhost:8000/health` (local) or `curl https://hanko.your-domain.com/health`
- Admin: `curl -k https://localhost:8001` or `curl https://hanko.your-domain.com/admin`
- Frontend: Open `https://hanko.your-domain.com` or `http://localhost:9500`
- MailSlurper: Open `http://localhost:8080`

## Automated Deployment

The `deploy.py` script handles:
- Container image builds and pushes
- Kubernetes manifest generation and application
- Vault secret injection
- Deployment readiness checks
- Health check validation

The Ansible playbook (`ansible/deploy.yml`) manages:
- Namespace creation
- Helm chart deployment
- Deployment verification

## Accessing the Application

- API: `https://hanko.your-domain.com` or `http://localhost:8000` (local)
- Admin: `https://hanko.your-domain.com/admin` or `http://localhost:8001` (local)
- Frontend: `https://hanko.your-domain.com` or `http://localhost:9500` (local)
- MailSlurper UI: `http://localhost:8080`

## Monitoring and Maintenance

- Check logs: `kubectl logs -n hanko -l app=hanko`
- Backup status: `kubectl logs -n hanko -l app=backups`
- Resource usage: `kubectl top pods -n hanko`
- Scale service: `kubectl scale deployment/hanko -n hanko --replicas=3`
- Test backup restoration:
  ```bash
  kubectl exec -n hanko -it $(kubectl get pods -n hanko -l app=backups -o name) -- bash
  gunzip /srv/hanko-postgres/backups/hanko-postgres-backup-<date>.gz
  psql -h postgres-hanko.dev.io -U hanko_user -d hanko < /srv/hanko-postgres/backups/hanko-postgres-backup-<date>
  ```

## Troubleshooting

- **Pods Not Starting**: `kubectl describe pod -n hanko <pod-name>`
- **TLS Issues**: Verify `hanko-tls` secret (`kubectl get secret hanko-tls -n hanko -o yaml`)
- **Vault Errors**: Check `VAULT_ADDR` and `VAULT_TOKEN`, ensure `secret/hanko` exists
- **Ingress Issues**: Verify ingress controller and DNS resolution
- **General Events**: `kubectl get events -n hanko`

## Notes

- Update `hanko.your-domain.com` in `helm/hanko/values.yaml` and DNS settings.
- Ensure a `standard` storage class exists or update `k8s/postgres.yml`.
- For non-Vault setups, provide static credentials in `helm/hanko/values.yaml`.
- Verify cert-manager is installed for production TLS.
## Deploy with Ansible

The stack ships two Ansible playbooks:

```bash
cd hanko/ansible
ansible-playbook -i inventory.ini deploy.yml       # local podman-compose deploy
ansible-playbook -i inventory.ini deploy-k8s.yml   # Helm/Kubernetes deploy
```
`deploy.yml` seeds `.env` from `.env.example` and generates local TLS certs
on first run. Validate playbook syntax with ansible-lint (containerised, no
host install needed) from the repo root:

```bash
ci/ansible-lint.sh
```
