## Hashicorp Boundary

<p align="left">
    <a href="https://github.com/robert-iw3/apps/actions/workflows/boundary-ghcr.yml" alt="Docker CI">
          <img src="https://github.com/robert-iw3/apps/actions/workflows/boundary-ghcr.yml/badge.svg" /></a>
</p>

<p align="center">
  <img src="https://www.hashicorp.com/_next/image?url=https%3A%2F%2Fwww.datocms-assets.com%2F2885%2F1714171044-blog-library-product-boundary-dark-gradient.jpg&w=3840&q=75" />
</p>

AWS Example:
<p align="center">
  <img src="https://raw.githubusercontent.com/hashicorp/boundary-reference-architecture/main/arch.png" />
</p>

# Boundary Deployment Guide

This guide provides instructions to deploy HashiCorp Boundary using Docker, Podman, Kubernetes, or Ansible with a focus on security and efficiency.

## Prerequisites

- **Docker/Podman**: Install Docker or Podman CLI.
- **Kubernetes**: Install `kubectl` and ensure access to a Kubernetes cluster.
- **Python**: Python 3.8+ for the automation script.
- **Ansible**: Ansible 2.9+ for the playbook, with `ansible-vault` for secrets.
- **Environment**: Copy `.env.example` to `.env` and update with secure values (for Docker/Podman/Kubernetes).
- **SSH Access**: For Ansible, ensure SSH access to the target host (localhost for testing).

## Deployment Steps

### Option 1: Docker/Podman
1. Ensure Docker or Podman is installed.
2. Copy `.env.example` to `.env` and update with secure values:
   ```bash
   cp .env.example .env
   nano .env
   ```
3. Run the deployment script:
   ```bash
   python deploy_boundary.py --type docker
   ```
   or
   ```bash
   python deploy_boundary.py --type podman
   ```

### Option 2: Kubernetes
1. Ensure `kubectl` is installed and configured.
2. Copy `.env.example` to `.env` and update with secure values:
   ```bash
   cp .env.example .env
   nano .env
   ```
3. Run the deployment script:
   ```bash
   python deploy_boundary.py --type kubernetes
   ```

### Option 3: Ansible
1. Ensure Ansible is installed on the control node.
2. Create an Ansible Vault password file (e.g., `.vault_pass.txt`):
   ```bash
   echo "your_vault_password" > .vault_pass.txt
   ```
3. Encrypt the vault file with secure secrets:
   ```bash
   ansible-vault encrypt vars/vault.yml --vault-password-file .vault_pass.txt
   ```
   Edit `vars/vault.yml` to set secure values for `vault_postgresql_password`, `vault_postgresql_replication_password`, `vault_boundary_root_key`, `vault_boundary_worker_auth_key`, and `vault_boundary_recovery_key`:
   ```bash
   ansible-vault edit vars/vault.yml --vault-password-file .vault_pass.txt
   ```
4. Update `inventory.yml` with the target host (default is localhost).
5. Run the playbook:
   ```bash
   ansible-playbook -i inventory.yml deploy_boundary.yml --vault-password-file .vault_pass.txt
   ```

## Accessing Boundary
- **API**: `http://localhost:9200`
- **Cluster**: `http://localhost:9201`
- **Proxy**: `http://localhost:9202`

## Security Notes
- Replace AEAD keys with a production KMS (e.g., AWS KMS) for production.
- Enable TLS by providing certificates in `/boundary/tls/` (Docker/Kubernetes).
- Restrict network access using firewall rules or Kubernetes NetworkPolicies.
- Use Ansible Vault to secure sensitive variables.

## Cleanup
- **Docker/Podman**:
  ```bash
  docker-compose -f docker-compose.yml down -v
  ```
- **Kubernetes**:
  ```bash
  kubectl delete -f boundary-kubernetes.yaml
  kubectl delete -f boundary-secrets.yaml
  ```
- **Ansible**:
  ```bash
  docker-compose -f /opt/boundary/docker-compose.yml down -v
  rm -rf /opt/boundary
  ```