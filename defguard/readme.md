# Defguard Deployment Guide

This guide provides instructions for deploying Defguard in a production environment using Docker, Podman, or Kubernetes, with Ansible for configuration management. The deployment is optimized for security, scalability, and zero trust principles.

## Prerequisites

- **Docker** or **Podman**: Install Docker (`docker.io`) or Podman for containerized deployment.
- **Kubernetes**: A production-grade Kubernetes cluster (e.g., EKS, GKE, AKS) with `kubectl` configured.
- **Ansible**: Install Ansible (`pip install ansible`).
- **Python**: Python 3.8+ for the deployment script.
- **TLS Certificates**: Valid TLS certificates for mTLS (self-signed or CA-issued).
- **Monitoring**: Prometheus and Grafana for metrics (optional but recommended).
- **Storage**: A storage class for Kubernetes PVCs (e.g., `standard`).

## Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/DefGuard/defguard.git
   cd defguard
   ```

2. **Configure Environment Variables**:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` with secure values:
     ```bash
     nano .env
     ```
     - Set strong passwords for `POSTGRES_PASSWORD` and `DEFGUARD_DEFAULT_ADMIN_PASSWORD`.
     - Generate a secure `DEFGUARD_SECRET_KEY`:
       ```bash
       openssl rand -hex 64
       ```
     - Generate a JWT token for `DEFGUARD_TOKEN` (consult Defguard documentation).
     - Specify paths to TLS certificates (`DEFGUARD_TLS_CERT`, `DEFGUARD_TLS_KEY`).

3. **Generate TLS Certificates** (if not using a CA):
   ```bash
   mkdir certs
   openssl req -x509 -newkey rsa:4096 -nodes -out certs/tls.crt -keyout certs/tls.key -days 365 -subj "/CN=defguard"
   ```

## Deployment Options

### Option 1: Docker Deployment
1. Ensure Docker and Docker Compose are installed.
2. Run the deployment script:
   ```bash
   python3 deploy.py --type docker
   ```
3. Verify services:
   ```bash
   docker-compose ps
   ```

### Option 2: Podman Deployment (Rootless)
1. Ensure Podman and Podman Compose are installed.
2. Run the deployment script:
   ```bash
   python3 deploy.py --type podman
   ```
3. Verify services:
   ```bash
   podman-compose ps
   ```

### Option 3: Kubernetes Deployment
1. Ensure `kubectl` is configured for your cluster.
2. Run the deployment script:
   ```bash
   python3 deploy.py --type kubernetes
   ```
3. Verify deployment:
   ```bash
   kubectl -n defguard get pods
   ```

### Ansible Configuration
The deployment script runs Ansible to configure the environment. To run independently:
```bash
ansible-playbook ansible/deploy.yml -e "deployment_type=<docker|podman|kubernetes>"
```

## Accessing Defguard
- **REST API**: `https://<DEFGUARD_COOKIE_DOMAIN>:8000`
- **gRPC**: `https://<DEFGUARD_COOKIE_DOMAIN>:50055` (mTLS required)
- **Proxy**: `https://<DEFGUARD_COOKIE_DOMAIN>:8080`
- **WireGuard**: UDP `<DEFGUARD_COOKIE_DOMAIN>:50051`
- **Admin Interface**: Access via `DEFGUARD_URL` with the admin password.

## Security Features
- **Zero Trust**: mTLS for gRPC, strict network policies, and restricted pod security.
- **Secrets Management**: Sensitive data stored in Kubernetes secrets or `.env` (chmod 640).
- **Non-Root Containers**: All containers run as non-root users.
- **Data Encryption**: PostgreSQL data checksums enabled for integrity.
- **Distroless Images**: Minimal runtime images reduce attack surface.
- **Resource Limits**: Prevent resource exhaustion with CPU/memory limits.
- **Health Checks**: Liveness and readiness probes ensure service reliability.

## Scaling and Monitoring
- **Horizontal Scaling**: Kubernetes HPA scales pods based on CPU usage (70% target).
- **Monitoring**: Prometheus metrics exposed at `/metrics` on port 8000.
- **Logging**: Logs stored in `/var/log/defguard` with daily rotation (7 days retention).
- **Backup**: Configure PostgreSQL backups (e.g., using `pg_dump`) separately.

## Troubleshooting
- Check logs:
  ```bash
  docker-compose logs
  # or
  kubectl -n defguard logs -l app=defguard
  ```
- Verify environment variables in `.env`.
- Ensure TLS certificates are valid and accessible.
- Check network policies and firewall rules.

## Cleanup
To remove the deployment:
- **Docker/Podman**:
  ```bash
  docker-compose down -v
  # or
  podman-compose down -v
  ```
- **Kubernetes**:
  ```bash
  kubectl delete namespace defguard
  ```

## Maintenance
- Update images regularly:
  ```bash
  docker pull ghcr.io/defguard/defguard:current
  docker pull ghcr.io/defguard/gateway:latest
  docker pull ghcr.io/defguard/defguard-proxy:current
  ```
- Rotate TLS certificates before expiration.
- Monitor disk usage for PostgreSQL data (`defguard-db` volume).

For further details, refer to the [Defguard Documentation](https://docs.defguard.net/).