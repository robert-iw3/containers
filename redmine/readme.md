# Redmine

## Overview
This project provides a production-ready deployment of [Redmine](https://www.redmine.org/), a flexible project management web application written in Ruby on Rails. It supports deployment via Docker, Podman, or Kubernetes, orchestrated using Ansible and configured via a YAML file.

## Redmine Version
- **Version**: 6.1.2 (latest stable as of September 2025)
- **Source**: https://www.redmine.org/releases/redmine-6.1.2.tar.gz
- **SHA256**: (To be updated with actual SHA256 for 6.1.2)

## Prerequisites
- Python 3.8+
- Ansible 2.10+
- Docker or Podman (for containerized deployments)
- Kubernetes (for K8s deployment)
- OpenSSL (for certificate generation)
- Valid SSL certificates in the `certs/` directory (or generate self-signed certificates)
- Configuration file: `config/deployment_config.yml`

## Setup Instructions

### 1. Generate Self-Signed Certificates
To generate self-signed CA and server certificates for Redmine:
```bash
chmod +x generate_certs.sh
./generate_certs.sh
```
This creates the following files in the `certs/` directory:
- `ca.crt`: CA certificate
- `redmine.crt`: Server certificate
- `redmine.key`: Server private key
- `dhparam.pem`: Diffie-Hellman parameters
- `ca.cnf`: CA configuration
- `server.cnf`: Server CSR configuration

Verify certificates:
```bash
openssl verify -CAfile certs/ca.crt certs/redmine.crt
```

### 2. Configure Deployment
Edit `config/deployment_config.yml` with your settings (e.g., PostgreSQL credentials, Redmine secret token, SMTP settings).

### 3. Run Unit Tests
To validate the deployment script:
```bash
python3 -m unittest test_deploy.py
```

### 4. Deploy Redmine
Run the deployment script with your desired target:
```bash
python3 deploy.py --target <docker|podman|kubernetes> --config config/deployment_config.yml
```
Example for Docker:
```bash
python3 deploy.py --target docker --config config/deployment_config.yml
```

### 5. Verify Deployment
- Check Docker/Podman services:
  ```bash
  docker-compose -f docker-compose.yml ps
  ```
- Verify HTTPS access:
  ```bash
  curl -I --cacert certs/ca.crt https://localhost:10445
  ```
- Validate HAProxy configuration:
  ```bash
  haproxy -c -f haproxy.cfg
  ```

## Directory Structure
- `ansible/`: Ansible playbooks and templates for deployment.
- `config/`: Configuration files (e.g., `deployment_config.yml`).
- `certs/`: SSL certificates and configuration files.
- `errors/`: Custom error pages for HAProxy.
- `generate_certs.sh`: Script to generate self-signed certificates.
- `test_deploy.py`: Unit tests for the deployment script.