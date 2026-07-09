## Hashicorp Vault

<p align="left">
    <a href="https://github.com/robert-iw3/apps/actions/workflows/vault-ghcr.yml" alt="Docker CI">
          <img src="https://github.com/robert-iw3/apps/actions/workflows/vault-ghcr.yml/badge.svg" /></a>
</p>

<p align="center">
  <img src="https://www.datocms-assets.com/2885/1620082983-blog-library-product-vault-dark-graphics.jpg" />
</p>

# Vault Deployment Guide

This guide provides instructions for deploying a secure HashiCorp Vault cluster using an Ansible playbook with Docker, Podman, or Kubernetes. TLS certificates are dynamically generated during the deployment process.

## Prerequisites
- **For Ansible**:
  - Ansible 2.9+ installed (`pip install ansible`)
  - Root or sudo access on the deployment host
- **For Docker/Podman**:
  - Docker or Podman installed
  - Docker Compose plugin (for Docker) or Podman Compose
- **For Kubernetes**:
  - Kubernetes cluster (v1.21+)
  - kubectl configured with cluster access
- **Common**:
  - Python 3.9+ with required packages: `pip install kubernetes pyyaml`
  - Vault binary installed (for Ansible dependency installation)
  - Sufficient resources (at least 1 node with 2GB RAM for Docker/Podman, or 3 nodes for Kubernetes)

## Directory Structure
```bash
vault-deployment/
├── certs/                    # Generated TLS certificates will be stored here
├── config/                   # Configuration files (vault-server.hcl, generate_certs.py)
├── vars/
│   └── vault.yml            # Ansible variables
├── deploy_vault.yml         # Ansible playbook
├── Dockerfile               # Vault Docker image
├── entrypoint.sh            # Entry point script
├── docker-compose.yml       # Docker/Podman configuration
└── vault-deployment.yaml    # Kubernetes manifest
```

## Deployment Steps

### Deploy with Ansible
1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Ansible and Dependencies**
   ```bash
   pip install ansible kubernetes pyyaml
   ```

3. **Configure Runtime**
   Edit `vars/vault.yml` to set `vault_runtime` to `docker`, `podman`, or `kubernetes`.

4. **Run the Ansible Playbook**
   ```bash
   ansible-playbook deploy_vault.yml
   ```
   The playbook automatically generates TLS certificates and deploys the Vault cluster.

## Verify Deployment
- **Kubernetes**:
  ```bash
  kubectl -n vault get pods
  ```
- **Docker/Podman**:
  ```bash
  docker compose -f docker-compose.yml ps
  # or
  podman compose -f docker-compose.yml ps
  ```

## Access Vault UI
- **Kubernetes**:
  ```bash
  kubectl -n vault port-forward service/vault 8200:8200
  ```
- **Docker/Podman**:
  The UI is directly accessible at `https://localhost:8200`

Access the UI at `https://localhost:8200`.

## Initialize Vault
After deployment, initialize Vault to obtain the unseal key and root token:
```bash
# For Docker/Podman
docker exec vault vault operator init -key-shares=1 -key-threshold=1

# For Kubernetes
kubectl -n vault exec -it vault-0 -- vault operator init -key-shares=1 -key-threshold=1
```

## Security Features
- TLS certificates dynamically generated during deployment
- Non-root container execution
- Resource limits to prevent resource exhaustion
- Health checks for service reliability
- Consul backend for high availability
- RBAC with least privilege principles (Kubernetes)

## Troubleshooting
- **Ansible**:
  - Check playbook logs for errors
  - Verify certificate generation: `ls certs/` (Docker/Podman) or pod logs (Kubernetes)
- **Kubernetes**:
  - Check pod logs: `kubectl -n vault logs -l app=vault`
  - Verify service status: `kubectl -n vault get svc`
- **Docker/Podman**:
  - Check container logs: `docker compose -f docker-compose.yml logs`
  - Verify services: `docker compose -f docker-compose.yml ps`

## Cleanup
- **Kubernetes**:
  ```bash
  kubectl delete -f vault-deployment.yaml
  kubectl delete namespace vault
  ```
- **Docker/Podman**:
  ```bash
  docker compose -f docker-compose.yml down -v
  # or
  podman compose -f docker-compose.yml down -v
  ```

## Notes
- TLS certificates are generated automatically during deployment using a Python script.
- The Docker/Podman deployment uses an init container to generate certificates, stored in a shared `vault-certs` volume.
- Kubernetes uses an init container to generate certificates, stored in an `emptyDir` volume.
- The Vault configuration integrates with a Consul backend for storage.
- Ensure the Consul service is accessible at `0.0.0.0:8501` for the storage backend.