# Apache NiFi and NiFi-Registry Deployment Automation

This repository provides an automated deployment solution for Apache NiFi and NiFi-Registry using Python, Ansible, and Podman. It sets up secure, containerized instances of NiFi and NiFi-Registry with TLS certificates, Prometheus monitoring, and S3 backups, optimized for a rootless Podman environment.

## Prerequisites

- **Operating System**: A Linux distribution (tested on Fedora/RHEL-based systems).
- **Tools**:
  - `podman` and `podman-compose` for container management.
  - `ansible` and `ansible-core` for automation.
  - `git` for cloning the repository.
  - `curl` for downloading dependencies.
  - `aws` CLI for S3 backups.
  - `certbot` for Let's Encrypt certificates.
- **Python**: Python 3.8+WITH `ansible-runner` (`pip install ansible-runner`).
- **Permissions**: Root or sudo access for initial setup.
- **AWS Credentials**: Valid AWS access key and secret key for S3 backups.
- **Domain**: A registered domain (e.g., `nifi.example.com`) for certificate generation.
- **Network**: Access to the internet for downloading binaries and certificates.

## Folder Structure

```
nifi-deployment-automation/
├── ansible/
│   ├── ansible.cfg              # Ansible configuration
│   ├── playbook.yml             # Ansible playbook for deployment
│   ├── secrets.yml              # Ansible Vault for sensitive data
│   └── templates/
│       ├── systemd-unit.j2      # Systemd unit template
│       ├── nifi/                # NiFi configuration templates
│       └── registry/            # NiFi-Registry configuration templates
├── docker/
│   ├── Dockerfile               # Dockerfile for Apache NiFi
│   └── registry.Dockerfile      # Dockerfile for NiFi-Registry
├── scripts/
│   ├── deploy_nifi.py           # Main Python deployment script
│   ├── nifi-backup-verify.sh    # Backup verification script
│   └── start.sh                 # Startup script for containers
├── backups/                     # Directory for backup storage (created at runtime)
├── logs/
│   └── deploy-nifi.log          # Deployment log file
├── prometheus/
│   └── prometheus.yml           # Prometheus configuration
└── .ansible_vault_pass.txt      # Ansible Vault password file
```

## Deployment Steps

1. **Clone the Repository**
   ```bash
   git clone <repository-url> nifi
   cd nifi-deployment-automation
   ```

2. **Configure AWS Credentials**
   - Edit `/home/nifi/.aws/credentials` (created during deployment) or provide valid AWS credentials in the `[default]` section:
     ```ini
     [default]
     aws_access_key_id = YOUR_ACCESS_KEY
     aws_secret_access_key = YOUR_SECRET_KEY
     ```
   - Ensure the file is owned by the `nifi` user and has `600` permissions.

3. **Update Configuration**
   - In `scripts/deploy_nifi.py`, update the `CONFIG` dictionary if needed:
     - `nifi_domain`: Set to your registered domain (e.g., `nifi.example.com`).
     - `s3_bucket`: Set to your S3 bucket name.
   - Ensure `ansible/templates/nifi/` and `ansible/templates/registry/` contain the necessary configuration templates (e.g., from the original NiFi/NiFi-Registry setup).

4. **Run the Deployment Script**
   ```bash
   sudo python3 scripts/deploy_nifi.py
   ```
   - The script performs the following:
     - Checks for required tools (`ansible`, `podman`, etc.).
     - Creates the `nifi` user and configures Podman subuid/subgid.
     - Installs Ansible and required collections.
     - Installs Certbot for TLS certificates.
     - Sets up Ansible Vault for secure storage of passwords.
     - Configures AWS CLI for S3 backups.
     - Validates playbook and template files.
     - Runs the Ansible playbook to deploy NiFi and NiFi-Registry.
     - Verifies the deployment by checking container status and web interfaces.
     - Sets up Prometheus monitoring and backup verification cron jobs.
   - Logs are written to `logs/deploy-nifi.log`.

5. **Verify Deployment**
   - Check the NiFi web interface at `https://<nifi_domain>:8443/nifi`.
   - Check the NiFi-Registry web interface at `https://<nifi_domain>:18080/nifi-registry`.
   - Verify Prometheus at `http://<host>:9090`.
   - Check logs for errors: `cat logs/deploy-nifi.log`.

## Key Features

- **Security**:
  - TLS certificates via Let's Encrypt or self-signed fallback.
  - Ansible Vault for sensitive data (passwords).
  - Rootless Podman with restricted sudo permissions.
  - Firewalld rules to limit network access.
- **Monitoring**:
  - Prometheus for NiFi, NiFi-Registry, and node-exporter metrics.
  - Exposed ports: 8443 (NiFi), 18080 (NiFi-Registry), 9100 (node-exporter), 9090 (Prometheus).
- **Backups**:
  - Daily S3 backups of NiFi data.
  - Cron job for backup verification with email alerts on failure.
- **Systemd Integration**:
  - Systemd services for NiFi, NiFi-Registry, and node-exporter.
  - Auto-updates via Podman auto-update timer.

## Troubleshooting

- **Deployment Fails**: Check `logs/deploy-nifi.log` for errors. Ensure all prerequisites are installed and AWS credentials are valid.
- **Web Interface Inaccessible**: Verify firewalld rules (`firewall-cmd --list-all --zone=drop`) and container status (`podman ps` as `nifi` user).
- **Certificate Issues**: Ensure the domain is correctly configured and accessible. Check `/etc/letsencrypt/live/<nifi_domain>` or fallback certificates in `/opt/nifi/certs`.
- **Backup Failures**: Verify AWS credentials and S3 bucket permissions. Check cron logs (`journalctl -u crond`).

## Notes

- **Sensitive Data**: Update `ansible/secrets.yml` with secure passwords and re-encrypt using `ansible-vault encrypt`.
- **Customization**: Modify `ansible/playbook.yml` for additional configurations (e.g., memory, CPUs, firewall rules).
- **Templates**: Ensure `ansible/templates/nifi/` and `ansible/templates/registry/` contain required configuration files (e.g., `nifi.properties`, `registry.properties`).
- **Permissions**: Run the script with sudo to allow user creation and system configuration.
- **Dependencies**: Install `ansible-runner` (`pip install ansible-runner`) before running the script.

## License

This project is licensed under the Apache License 2.0, consistent with Apache NiFi and NiFi-Registry.