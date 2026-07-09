
<p align="center">
  <img src="https://repository-images.githubusercontent.com/14125254/27f3ac80-6a20-11ea-8e4a-7151721107d3" />
</p>

# Consul Deployment Guide

This guide provides instructions for deploying a secure and highly available Consul cluster using an Ansible playbook with Docker, Podman, or Kubernetes. TLS certificates are dynamically generated during the deployment process.

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
  - Consul binary installed (for certificate generation)
  - Sufficient resources (at least 3 nodes with 2GB RAM each for Kubernetes, or 2GB RAM for Docker/Podman)

## Directory Structure
```bash
consul-deployment/
├── certs/                    # Generated TLS certificates will be stored here
├── config/                   # Configuration files (e.g., vault-storage.json)
├── vars/
│   └── consul.yml           # Ansible variables
├── deploy_consul.yml        # Ansible playbook
├── docker-compose.yml       # Docker/Podman configuration
└── consul-deployment.yaml   # Kubernetes manifest
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
   Edit `vars/consul.yml` to set `consul_runtime` to `docker`, `podman`, or `kubernetes`.

4. **Run the Ansible Playbook**
   ```bash
   ansible-playbook deploy_consul.yml
   ```
   The playbook automatically generates TLS certificates and deploys the Consul cluster.

## Verify Deployment
- **Kubernetes**:
  ```bash
  kubectl -n consul get pods
  ```
- **Docker/Podman**:
  ```bash
  docker compose -f docker-compose.yml ps
  # or
  podman compose -f docker-compose.yml ps
  ```

## Access Consul UI
- **Kubernetes**:
  ```bash
  kubectl -n consul port-forward service/consul 8501:8501
  ```
- **Docker/Podman**:
  The UI is directly accessible at `https://localhost:8501`

Access the UI at `https://localhost:8501`.

## Security Features
- TLS certificates dynamically generated during deployment
- Gossip encryption (Kubernetes uses Secrets, Docker/Podman embeds in config)
- RBAC with least privilege principles (Kubernetes)
- Non-root container execution
- Resource limits to prevent resource exhaustion
- Health checks for service reliability

## Troubleshooting
- **Ansible**:
  - Check playbook logs for errors
  - Verify certificate generation: `ls certs/`
- **Kubernetes**:
  - Check pod logs: `kubectl -n consul logs -l app=consul`
  - Verify service status: `kubectl -n consul get svc`
- **Docker/Podman**:
  - Check container logs: `docker compose -f docker-compose.yml logs`
  - Verify services: `docker compose -f docker-compose.yml ps`

## Cleanup
- **Kubernetes**:
  ```bash
  kubectl delete -f consul-deployment.yaml
  kubectl delete namespace consul
  ```
- **Docker/Podman**:
  ```bash
  docker compose -f docker-compose.yml down -v
  # or
  podman compose -f docker-compose.yml down -v
  ```

## Notes
- TLS certificates are generated automatically during deployment and stored in a shared volume (Docker/Podman) or emptyDir (Kubernetes).
- The Ansible playbook ensures dependencies are installed and verifies deployment health.
- The Docker/Podman deployment uses init containers to generate certificates.
- Kubernetes uses an init container to generate certificates, with the CA certificate created only by the first pod.