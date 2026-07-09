# Burp Suite Deployment Guide

This guide provides instructions to deploy Burp Suite Professional using Docker Compose, Podman Compose, or Kubernetes. The setup is optimized for security and functionality, using a non-root user, persistent storage, and resource limits.

## Prerequisites

- **Docker** or **Podman** installed for containerized deployment.
- **Kubernetes** cluster (e.g., minikube, OpenShift) for Kubernetes deployment.
- **Burp Suite Professional License Key** (`BURP_KEY`).
- **PortSwigger Account** credentials and Burp Suite version details:
  - `PORTSWIGGER_EMAIL_ADDRESS`
  - `PORTSWIGGER_PASSWORD`
  - `BURP_SUITE_PRO_VERSION` (e.g., 2025.8.2)
  - `BURP_SUITE_PRO_CHECKSUM` (SHA256 checksum of the JAR file)
- **X11 Server** (e.g., XQuartz on macOS, Xming on Windows) for GUI support.

## Directory Structure

```
burp-suite-deployment/
├── config/
│   └── project_options.json
├── deploy_burp.py
├── Dockerfile
├── docker-compose.yml
├── download.sh
├── entrypoint.sh
├── burp-deployment.yaml
└── README.md
```

## Deployment Instructions

```bash
python3 deploy_burp.py
```

### 1. Docker Compose

1. **Set Environment Variables**:
   ```bash
   export PORTSWIGGER_EMAIL_ADDRESS="your-email@example.com"
   export PORTSWIGGER_PASSWORD="your-password"
   export BURP_SUITE_PRO_VERSION="2025.8.2"
   export BURP_SUITE_PRO_CHECKSUM="your-sha256-checksum"
   export BURP_KEY="your-burp-license-key"
   ```

2. **Start X11 Server**:
   - On macOS: Install and start XQuartz, enable "Allow connections from network clients" in Preferences > Security.
   - On Windows: Install and start Xming.
   - On Linux: Ensure an X11 server is running.

3. **Deploy with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Access Burp Suite**:
   - Configure your browser to use the proxy at `127.0.0.1:8080`.
   - Install the Burp Suite CA certificate in your browser for HTTPS traffic.

5. **Stop the Service**:
   ```bash
   docker-compose down
   ```

### 2. Podman Compose

1. **Install Podman Compose**:
   ```bash
   pipx install podman-compose
   pipx ensurepath
   ```

2. **Set Environment Variables** (same as Docker Compose).
3. **Start X11 Server** (same as Docker Compose).
4. **Deploy with Podman Compose**:
   ```bash
   podman-compose up -d
   ```

5. **Access and Stop** (same as Docker Compose).

### 3. Kubernetes

1. **Set Up Secrets**:
   ```bash
   kubectl create secret generic burp-secrets \
     --from-literal=burp-key="your-burp-license-key" \
     -n burp-suite
   ```

2. **Build and Push Docker Image**:
   ```bash
   docker build -t your-registry/burp-suite-pro:latest \
     --build-arg PORTSWIGGER_EMAIL_ADDRESS="your-email@example.com" \
     --build-arg PORTSWIGGER_PASSWORD="your-password" \
     --build-arg BURP_SUITE_PRO_VERSION="2025.8.2" \
     --build-arg BURP_SUITE_PRO_CHECKSUM="your-sha256-checksum" .
   docker push your-registry/burp-suite-pro:latest
   ```

3. **Update Image in Manifest**:
   Edit `burp-deployment.yaml` to replace `burp-suite-pro:latest` with `your-registry/burp-suite-pro:latest`.

4. **Deploy to Kubernetes**:
   ```bash
   kubectl apply -f burp-deployment.yaml
   ```

5. **Access Burp Suite**:
   - Expose the service locally:
     ```bash
     kubectl port-forward svc/burp-suite 8080:8080 -n burp-suite
     ```
   - Configure your browser to use `127.0.0.1:8080`.

6. **Clean Up**:
   ```bash
   kubectl delete -f burp-deployment.yaml
   ```

## Notes

- **Proxy Configuration**: The proxy listener is set to bind to all interfaces on port 8080 (`config/project_options.json`).
- **Persistence**: Configuration and license data are stored in the `burp-data` volume (Docker/Podman) or PVC (Kubernetes).
- **Security**: Runs as non-root user `burp` (UID 1000). Kubernetes includes a network policy to restrict traffic.
- **Troubleshooting**:
  - Check logs: `docker-compose logs` or `kubectl logs -n burp-suite`.
  - Ensure X11 server is running for GUI access.
  - Verify environment variables and network connectivity.

For further support, visit the [PortSwigger Support Center](https://portswigger.net/support).