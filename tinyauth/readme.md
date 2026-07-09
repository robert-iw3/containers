# TinyAuth Automated Deployment

This repository provides an automated deployment solution for the TinyAuth application, supporting Docker, Podman, Kubernetes, and Ansible. The deployment is initiated via a Python script and includes security best practices to support a wide range of applications.

## Prerequisites

- Python 3.8+
- Docker or Podman
- Kubernetes (kubectl) for Kubernetes deployment
- Ansible for Ansible deployment
- Administrative access to the target system
- Valid DNS records for `tinyauth.example.com` and `whoami.example.com`
- SSL/TLS certificates (recommended for production)

## Security Best Practices Implemented

- Secure random secret generation for TinyAuth
- Restricted file permissions for sensitive configuration (`.env`)
- Container restart policies for reliability
- Resource limits in Kubernetes deployment
- Secure cookie settings enabled by default
- Read-only volume mounts where possible
- Traefik as a reverse proxy for secure routing
- Namespace isolation in Kubernetes

## Deployment Methods

### 1. Docker Compose
Deploys TinyAuth with Traefik and a Whoami test service using Docker Compose.

```bash
python deploy_tinyauth.py --method docker
```

### 2. Podman Compose
Deploys using Podman Compose, suitable for rootless container management.

```bash
python deploy_tinyauth.py --method podman
```

### 3. Kubernetes
Deploys to a Kubernetes cluster with Traefik ingress and resource limits.

```bash
python deploy_tinyauth.py --method kubernetes
```

Ensure your `kubectl` context is set to the target cluster and the `tinyauth` namespace exists:

```bash
kubectl create namespace tinyauth
```

### 4. Ansible
Deploys using Ansible with Podman as the container runtime.

```bash
python deploy_tinyauth.py --method ansible
```

Ensure Ansible is configured with access to the target hosts (inventory file).

## Configuration

1. **Environment Variables**:
   - The script automatically generates a secure `.env` file based on `.env.example`.
   - Modify `.env` for custom configurations (e.g., OAuth settings, users).
   - For production, update `APP_URL` and ensure `COOKIE_SECURE=true`.

2. **DNS Configuration**:
   - Configure `tinyauth.example.com` and `whoami.example.com` to point to your server.
   - For Kubernetes, ensure your ingress controller is properly set up.

3. **TLS/SSL**:
   - For production, configure Traefik with Let's Encrypt or provide SSL certificates.
   - Update `compose.yml` or `k8s/tinyauth-deployment.yml` to enable HTTPS.

## Usage

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd tinyauth-deployment
   ```

2. Run the deployment script with your preferred method:
   ```bash
   python deploy_tinyauth.py --method <docker|podman|kubernetes|ansible>
   ```

3. Verify the deployment:
   - Access `http://tinyauth.example.com` for the TinyAuth login page.
   - Access `http://whoami.example.com` to test authentication.

## Adding Support for Other Applications

To protect additional applications with TinyAuth:

1. **Docker/Podman**:
   - Add new services to `compose.yml` with Traefik labels:
     ```yaml
     labels:
       traefik.enable: true
       traefik.http.routers.<app>.rule: Host(`<app>.example.com`)
       traefik.http.routers.<app>.middlewares: tinyauth
     ```

2. **Kubernetes**:
   - Add new services and IngressRoute resources in `k8s/` directory.
   - Reference the `tinyauth-auth` middleware for authentication.

3. **Ansible**:
   - Update `ansible/tinyauth-playbook.yml` with additional `podman_container` tasks for new services.

## Troubleshooting

- Check container logs:
  ```bash
  docker logs tinyauth
  podman logs tinyauth
  kubectl logs -n tinyauth -l app=tinyauth
  ```

- Verify Traefik dashboard (http://<server>:80/dashboard/) for routing issues.
- Ensure DNS records are correctly configured.
- Check `.env` for correct `SECRET` and `APP_URL` values.

## Contributing

Contributions are welcome! Please submit pull requests or open issues for improvements or bug fixes.

## License

MIT License