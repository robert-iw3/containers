#!/bin/bash
set -euo pipefail

# Configuration - customize as needed
NAMESPACE="sonarqube"
SECRET_NAME="traefik-certs"
CERT_DIR="./certs"
MANIFEST_FILE="deploy.yaml"
DOMAINS=("sonarqube.io" "traefik.testing.io")
CA_SUBJECT="/C=US/ST=State/L=City/O=Organization/OU=Unit/CN=SonarQubeCA"
CERT_SUBJECT="/C=US/ST=State/L=City/O=Organization/OU=Unit/CN="
CERT_DAYS=365
KUBECTL="kubectl"
OPENSSL="openssl"
POSTGRESQL_IMAGE="docker.io/bitnami/postgresql:latest"
SONARQUBE_IMAGE="docker.io/sonarqube:latest"
POSTGRESQL_USERNAME="sonar"
POSTGRESQL_PASSWORD="sonar_password"
POSTGRESQL_DATABASE="sonarqube"
POSTGRESQL_REPLICATION_USER="repl_user"
POSTGRESQL_REPLICATION_PASSWORD="repl_password"
POSTGRESQL_HOSTNAME="postgres.sonarqube.svc.cluster.local"
BACKUP_POSTGRESQL_HOSTNAME="backup-postgres"
SONARQUBE_HOSTNAME="sonarqube.sonarqube.svc.cluster.local"
TRAEFIK_AUTH_HASHED_PASSWORD="$(openssl passwd -6 'your_secure_password')" # Replace with secure password

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

check_requirements() {
    for cmd in "${KUBECTL}" "${OPENSSL}"; do
        if ! command -v "${cmd}" >/dev/null 2>&1; then
            log "ERROR: ${cmd} is required but not installed."
            exit 1
        fi
    done
}

setup_cert_directory() {
    log "Creating certificate directory: ${CERT_DIR}"
    mkdir -p "${CERT_DIR}"
    chmod 700 "${CERT_DIR}"
}

generate_ca_cert() {
    log "Generating CA certificate"
    "${OPENSSL}" req -x509 -newkey rsa:4096 -nodes \
        -keyout "${CERT_DIR}/sonarqube.ca.key" \
        -out "${CERT_DIR}/sonarqube.ca.pem" \
        -days "${CERT_DAYS}" \
        -subj "${CA_SUBJECT}" 2>/dev/null || {
        log "ERROR: Failed to generate CA certificate."
        exit 1
    }
    chmod 600 "${CERT_DIR}/sonarqube.ca.key" "${CERT_DIR}/sonarqube.ca.pem"
}

generate_domain_certs() {
    for domain in "${DOMAINS[@]}"; do
        log "Generating certificate for ${domain}"
        cert_subject="${CERT_SUBJECT}${domain}"
        "${OPENSSL}" req -newkey rsa:2048 -nodes \
            -keyout "${CERT_DIR}/${domain}-key.pem" \
            -out "${CERT_DIR}/${domain}.csr" \
            -subj "${cert_subject}" 2>/dev/null || {
            log "ERROR: Failed to generate CSR for ${domain}."
            exit 1
        }
        "${OPENSSL}" x509 -req \
            -in "${CERT_DIR}/${domain}.csr" \
            -CA "${CERT_DIR}/sonarqube.ca.pem" \
            -CAkey "${CERT_DIR}/sonarqube.ca.key" \
            -CAcreateserial \
            -out "${CERT_DIR}/${domain}.pem" \
            -days "${CERT_DAYS}" 2>/dev/null || {
            log "ERROR: Failed to sign certificate for ${domain}."
            exit 1
        }
        chmod 600 "${CERT_DIR}/${domain}-key.pem" "${CERT_DIR}/${domain}.pem"
        rm -f "${CERT_DIR}/${domain}.csr" "${CERT_DIR}/sonarqube.ca.srl"
    done
}

generate_letsencrypt_certs() {
    log "Generating Let's Encrypt certificates using certbot"
    if ! command -v certbot >/dev/null 2>&1; then
        log "ERROR: certbot is required for Let's Encrypt but not installed."
        exit 1
    fi
    for domain in "${DOMAINS[@]}"; do
        certbot certonly --standalone \
            -d "${domain}" \
            --non-interactive \
            --agree-tos \
            --email "admin@${domain}" \
            --cert-path "${CERT_DIR}/${domain}.pem" \
            --key-path "${CERT_DIR}/${domain}-key.pem" || {
            log "ERROR: Failed to generate Let's Encrypt certificate for ${domain}."
            exit 1
        }
    done
    # Copy a placeholder CA certificate (not used with Let's Encrypt)
    cp "${CERT_DIR}/sonarqube.io.pem" "${CERT_DIR}/sonarqube.ca.pem"
}

create_k8s_secret() {
    log "Creating Kubernetes Secret: ${SECRET_NAME}"
    "${KUBECTL}" create secret generic "${SECRET_NAME}" \
        --namespace "${NAMESPACE}" \
        --from-file=sonarqube.ca.pem="${CERT_DIR}/sonarqube.ca.pem" \
        --from-file=sonarqube.testing.io.pem="${CERT_DIR}/sonarqube.testing.io.pem" \
        --from-file=sonarqube.testing.io-key.pem="${CERT_DIR}/sonarqube.testing.io-key.pem" \
        --dry-run=client -o yaml | "${KUBECTL}" apply -f - || {
        log "ERROR: Failed to create or update Kubernetes Secret."
        exit 1
    }
}

apply_manifest() {
    log "Applying ${MANIFEST_FILE}"
    "${KUBECTL}" apply -f "${MANIFEST_FILE}" || {
        log "ERROR: Failed to apply Kubernetes manifest."
        exit 1
    }
}

verify_deployment() {
    log "Verifying deployment in namespace ${NAMESPACE}"
    "${KUBECTL}" get pods,svc,ingressroute -n "${NAMESPACE}" || {
        log "WARNING: Failed to retrieve resources. Check deployment status manually."
    }
}

main() {
    log "Starting certificate generation and deployment process"
    check_requirements
    setup_cert_directory
    #generate_letsencrypt_certs
    generate_ca_cert
    generate_domain_certs
    create_k8s_secret
    apply_manifest
    verify_deployment
    log "Deployment completed successfully"
}

main && "${KUBECTL}" get ns "${NAMESPACE}" >/dev/null 2>&1 || "${KUBECTL}" create ns "${NAMESPACE}"