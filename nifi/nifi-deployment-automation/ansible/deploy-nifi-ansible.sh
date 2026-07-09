#!/bin/bash
set -euo pipefail

# Configuration
ANSIBLE_PLAYBOOK="deploy-nifi.yml"
SYSTEMD_TEMPLATE="systemd-unit.j2"
ANSIBLE_VAULT_FILE="secrets.yml"
ANSIBLE_VAULT_PASSWORD_FILE="/home/nifi/.ansible_vault_pass.txt"
NIFI_DOMAIN="nifi.example.com"
S3_BUCKET="bucket"
BACKUP_DIR="/home/nifi/backups"
LOG_FILE="/home/nifi/deploy-nifi.log"
PODMAN_SYSTEMD_USER="nifi"
AWS_CREDENTIALS_FILE="/home/${PODMAN_SYSTEMD_USER}/.aws/credentials"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

check_requirements() {
    log "Checking for required tools"
    local tools=("ansible" "ansible-playbook" "podman" "git" "curl" "aws")
    for cmd in "${tools[@]}"; do
        if ! command -v "${cmd}" >/dev/null 2>&1; then
            log "ERROR: ${cmd} is required but not installed."
            exit 1
        fi
    done
}

create_nifi_user() {
    log "Creating NiFi user and configuring environment"
    if ! id "${PODMAN_SYSTEMD_USER}" >/dev/null 2>&1; then
        sudo useradd -m -s /bin/bash -G wheel,systemd-journal "${PODMAN_SYSTEMD_USER}"
        log "Created NiFi user: ${PODMAN_SYSTEMD_USER}"
    else
        log "NiFi user ${PODMAN_SYSTEMD_USER} already exists"
    fi

    # Configure subuid and subgid for rootless Podman
    if ! grep -q "^${PODMAN_SYSTEMD_USER}:" /etc/subuid; then
        sudo bash -c "echo '${PODMAN_SYSTEMD_USER}:165536:65536' >> /etc/subuid"
    fi
    if ! grep -q "^${PODMAN_SYSTEMD_USER}:" /etc/subgid; then
        sudo bash -c "echo '${PODMAN_SYSTEMD_USER}:165536:65536' >> /etc/subgid"
    fi

    # Enable lingering for user systemd services
    sudo loginctl enable-linger "${PODMAN_SYSTEMD_USER}" || {
        log "WARNING: Failed to enable lingering for ${PODMAN_SYSTEMD_USER}. User services may not persist."
    }

    # Allow passwordless sudo for Podman and systemctl
    sudo bash -c "cat > /etc/sudoers.d/nifi << EOF
${PODMAN_SYSTEMD_USER} ALL=(ALL) NOPASSWD:/usr/bin/podman,/bin/systemctl
EOF"
    sudo chmod 0440 /etc/sudoers.d/nifi
    sudo visudo -cf /etc/sudoers.d/nifi || {
        log "ERROR: Invalid sudoers configuration."
        exit 1
    }
}

install_ansible() {
    log "Installing Ansible and required collections as ${PODMAN_SYSTEMD_USER}"
    sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "pip3 install --user ansible ansible-core" || {
        log "ERROR: Failed to install Ansible for ${PODMAN_SYSTEMD_USER}."
        exit 1
    }
    sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "ansible-galaxy collection install community.crypto containers.podman --force" || {
        log "ERROR: Failed to install Ansible collections."
        exit 1
    }
}

install_certbot() {
    log "Installing certbot"
    sudo dnf install -y certbot python3-certbot || {
        log "ERROR: Failed to install certbot."
        exit 1
    }
}

setup_vault() {
    log "Setting up Ansible Vault for secrets"
    if [ ! -f "${ANSIBLE_VAULT_PASSWORD_FILE}" ]; then
        sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "openssl rand -base64 32 > ${ANSIBLE_VAULT_PASSWORD_FILE}"
        sudo -u "${PODMAN_SYSTEMD_USER}" chmod 600 "${ANSIBLE_VAULT_PASSWORD_FILE}"
        log "Generated vault password file: ${ANSIBLE_VAULT_PASSWORD_FILE}"
    fi

    if [ ! -f "${ANSIBLE_VAULT_FILE}" ]; then
        sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "cat > ${ANSIBLE_VAULT_FILE} << EOF
vault_nifi_password: securePassword123
vault_jks_password: secureKeystore123
EOF"
        sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "ansible-vault encrypt ${ANSIBLE_VAULT_FILE} --vault-password-file ${ANSIBLE_VAULT_PASSWORD_FILE}" || {
            log "ERROR: Failed to encrypt vault file."
            exit 1
        }
        log "Created and encrypted vault file: ${ANSIBLE_VAULT_FILE}"
    fi
}

configure_aws() {
    log "Configuring AWS CLI for S3 backups"
    if [ ! -f "${AWS_CREDENTIALS_FILE}" ]; then
        sudo -u "${PODMAN_SYSTEMD_USER}" mkdir -p "$(dirname "${AWS_CREDENTIALS_FILE}")"
        sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "cat > ${AWS_CREDENTIALS_FILE} << EOF
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
EOF"
        sudo -u "${PODMAN_SYSTEMD_USER}" chmod 600 "${AWS_CREDENTIALS_FILE}"
        log "WARNING: AWS credentials file created with placeholder values. Update ${AWS_CREDENTIALS_FILE} with valid credentials."
    fi
}

validate_files() {
    log "Validating playbook and template files"
    for file in "${ANSIBLE_PLAYBOOK}" "${SYSTEMD_TEMPLATE}"; do
        if [ ! -f "${file}" ]; then
            log "ERROR: ${file} not found."
            exit 1
        fi
    done
    sudo -u "${PODMAN_SYSTEMD_USER}" chmod 644 "${ANSIBLE_PLAYBOOK}" "${SYSTEMD_TEMPLATE}"
}

run_playbook() {
    log "Running Ansible playbook as ${PODMAN_SYSTEMD_USER}: ${ANSIBLE_PLAYBOOK}"
    sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "ansible-playbook ${ANSIBLE_PLAYBOOK} --vault-password-file ${ANSIBLE_VAULT_PASSWORD_FILE} -e 'nifi_domain=${NIFI_DOMAIN}'" || {
        log "ERROR: Failed to run Ansible playbook."
        exit 1
    }
}

verify_deployment() {
    log "Verifying NiFi deployment"
    if ! sudo -u "${PODMAN_SYSTEMD_USER}" podman ps | grep -q nifi; then
        log "ERROR: NiFi container is not running."
        exit 1
    fi
    if ! systemctl is-active --quiet container-nifi.service; then
        log "ERROR: NiFi service is not active."
        exit 1
    fi
    if ! sudo -u "${PODMAN_SYSTEMD_USER}" curl -k -s -f "https://${NIFI_DOMAIN}:8443/nifi" >/dev/null; then
        log "WARNING: NiFi web interface not accessible at https://${NIFI_DOMAIN}:8443/nifi."
    else
        log "NiFi web interface is accessible."
    fi
}

setup_monitoring() {
    log "Setting up Prometheus monitoring"
    PROMETHEUS_CONFIG="/home/${PODMAN_SYSTEMD_USER}/prometheus/prometheus.yml"
    sudo -u "${PODMAN_SYSTEMD_USER}" mkdir -p "$(dirname "${PROMETHEUS_CONFIG}")"
    sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "cat > ${PROMETHEUS_CONFIG} << EOF
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'nifi'
    static_configs:
      - targets: ['${NIFI_DOMAIN}:8443']
    metrics_path: /nifi-metrics
    scheme: https
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
EOF"
    sudo -u "${PODMAN_SYSTEMD_USER}" chmod 644 "${PROMETHEUS_CONFIG}"
    sudo -u "${PODMAN_SYSTEMD_USER}" podman run -d --name prometheus --network nifi -p 9090:9090 -v "${PROMETHEUS_CONFIG}:/etc/prometheus/prometheus.yml:Z" prom/prometheus:latest || {
        log "WARNING: Failed to start Prometheus container."
    }
}

setup_backup_verification() {
    log "Setting up backup verification"
    sudo -u "${PODMAN_SYSTEMD_USER}" mkdir -p "${BACKUP_DIR}"
    sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "cat > /home/${PODMAN_SYSTEMD_USER}/nifi-backup-verify.sh << EOF
#!/bin/bash
aws s3 ls s3://${S3_BUCKET}/nifi-backup-\$(date +%Y%m%d).tar.gz || {
    echo 'Backup for \$(date +%Y%m%d) not found!' | mail -s 'NiFi Backup Failure' admin@example.com
}
EOF"
    sudo -u "${PODMAN_SYSTEMD_USER}" chmod +x "/home/${PODMAN_SYSTEMD_USER}/nifi-backup-verify.sh"
    sudo -u "${PODMAN_SYSTEMD_USER}" bash -c "cat > /home/${PODMAN_SYSTEMD_USER}/nifi-backup.cron << EOF
0 3 * * * /home/${PODMAN_SYSTEMD_USER}/nifi-backup-verify.sh
EOF"
    sudo -u "${PODMAN_SYSTEMD_USER}" crontab "/home/${PODMAN_SYSTEMD_USER}/nifi-backup.cron"
    log "Configured backup verification cron job for ${PODMAN_SYSTEMD_USER}"
}

cleanup() {
    log "Cleaning up temporary files"
    # Add cleanup for any temporary files if needed
}

main() {
    log "Starting NiFi deployment process at $(date '+%Y-%m-%d %H:%M:%S')"
    check_requirements
    create_nifi_user
    install_ansible
    install_certbot
    setup_vault
    configure_aws
    validate_files
    run_playbook
    verify_deployment
    setup_monitoring
    setup_backup_verification
    log "Deployment completed successfully at $(date '+%Y-%m-%d %H:%M:%S')"
}

trap cleanup EXIT

main