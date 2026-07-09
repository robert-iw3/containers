# Authentik Deployment Guide

This guide provides step-by-step instructions to deploy Authentik, an open-source identity provider, using Docker, Podman, or Kubernetes. The deployment is optimized for security and functionality to support various applications.

## Prerequisites

- **Docker or Podman**: Install Docker (or Podman) and `docker-compose` (or `podman-compose`).
- **Kubernetes**: For Kubernetes deployment, ensure `kubectl` is configured and you have access to a cluster.
- **Python 3**: Required for the deployment script.
- **Access to Ports**: Ensure ports `9000` (HTTP) and `9443` (HTTPS) are available.
- **Storage**: Allocate at least 10GB for PostgreSQL data and backups.

## Directory Structure

Ensure the following files are in your working directory:
- `deploy.py`: Python script for deployment.
- `prod-docker-compose.yml`: Docker Compose configuration.
- `authentik-k8s.yml`: Kubernetes manifest.
- `.env.example`: Template for environment variables.
- `Makefile`: Simplifies deployment tasks.
- `haproxy.cfg`: Configuration for Docker socket proxy.

## Deployment Steps

### 1. Generate Environment Variables

Create a `.env` file with secure defaults:

```bash
make generate-env
```

This runs `deploy.py --generate-env` to create a `.env` file. Edit the file to set your email configuration:

- `AUTHENTIK_EMAIL__HOST`: Your SMTP server (e.g., `smtp.example.com`).
- `AUTHENTIK_EMAIL__PORT`: SMTP port (e.g., `587`).
- `AUTHENTIK_EMAIL__USERNAME`: SMTP username (if required).
- `AUTHENTIK_EMAIL__PASSWORD`: SMTP password (if required).
- `AUTHENTIK_EMAIL__FROM`: Email address Authentik sends from (e.g., `authentik@example.com`).

### 2. Deploy Authentik

Choose your deployment method: Docker, Podman, or Kubernetes.

#### Option 1: Docker

```bash
make deploy-docker
```

This deploys Authentik using `prod-docker-compose.yml`.

#### Option 2: Podman

Ensure the Podman socket is enabled:

```bash
systemctl --user enable podman.socket
systemctl --user start podman.socket
```

Then deploy:

```bash
make deploy-podman
```

#### Option 3: Kubernetes

Ensure `kubectl` is configured and you have cluster access. Deploy with:

```bash
make deploy-k8s
```

This applies `authentik-k8s.yml` to your cluster.

### 3. Access Authentik

- **HTTP**: `http://<your-host>:9000`
- **HTTPS**: `https://<your-host>:9443`

The default admin credentials are set during the initial setup. Access the Authentik web interface to configure them.

### 4. Configure TLS (Optional, Recommended for Production)

For secure HTTPS:
- Place TLS certificates in the `./certs` directory.
- Update `prod-docker-compose.yml` or `authentik-k8s.yml` to use them.
- Alternatively, use a reverse proxy (e.g., Traefik or Nginx) with Let’s Encrypt.

### 5. Verify Deployment

- Check service health:
  ```bash
  docker-compose -f prod-docker-compose.yml ps
  ```
  or
  ```bash
  kubectl get pods -n authentik
  ```
- Ensure all services (postgresql, redis, server, worker, docker-socket-proxy, backups) are running.

### 6. Manage Backups

Backups are stored in the `authentik-postgres-backups` volume (Docker) or a persistent volume (Kubernetes). They are created daily and retained for 7 days. Check logs for backup errors:

```bash
docker logs postgres2-authentik
```

or

```bash
kubectl logs -n authentik -l app=postgresql
```

## Cleanup

To remove the deployment:

```bash
make clean
```

This stops and removes containers (Docker/Podman) or deletes Kubernetes resources.

## Troubleshooting

- **Environment Errors**: Ensure all required variables in `.env` are set. Re-run `make generate-env` if needed.
- **Service Failures**: Check logs (e.g., `docker logs authentik-server` or `kubectl logs -n authentik -l app=authentik-server`).
- **Port Conflicts**: Verify ports `9000` and `9443` are free.
- **Podman Socket**: Ensure the Podman socket is running for Podman deployments.

## Additional Configuration

- **Monitoring**: Enable Prometheus metrics in Authentik for monitoring (see Authentik documentation).
- **Scaling**: For Kubernetes, scale workers by editing `replicas` in `authentik-k8s.yml`.
- **Secrets Management**: For enhanced security, integrate with a secrets manager like HashiCorp Vault.

For more details, refer to the [Authentik Documentation](https://goauthentik.io/docs/).