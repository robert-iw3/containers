#!/bin/bash
set -euo pipefail

# Configuration
NAMESPACE="keycloak"
MANIFEST_FILE="deploy.yaml"
KUBECTL="kubectl"

POSTGRESQL_USERNAME="keycloak"
POSTGRESQL_PASSWORD="keycloak_password"
POSTGRESQL_DATABASE="keycloak"
POSTGRESQL_REPLICATION_USER="repl_user"
POSTGRESQL_REPLICATION_PASSWORD="repl_password"
KEYCLOAK_USER="admin"
KEYCLOAK_PASSWORD="admin_password"
DB_VENDOR="postgres"
DB_ADDR="postgres.keycloak.svc.cluster.local"
JGROUPS_DISCOVERY_PROTOCOL="dns.DNS_PING"
JGROUPS_DISCOVERY_PROPERTIES="dns_query=keycloak.keycloak.svc.cluster.local"
PROXY_ADDRESS_FORWARDING="true"
KEYCLOAK_LOGLEVEL="INFO"
TRAEFIK_AUTH_HASHED_PASSWORD="$(openssl passwd -6 'traefik_secure_password')" # Replace with secure password

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

check_requirements() {
    for cmd in "${KUBECTL}" openssl; do
        if ! command -v "${cmd}" >/dev/null 2>&1; then
            log "ERROR: ${cmd} is required but not installed."
            exit 1
        fi
    done
}

ensure_namespace() {
    log "Ensuring namespace ${NAMESPACE} exists"
    "${KUBECTL}" get ns "${NAMESPACE}" >/dev/null 2>&1 || "${KUBECTL}" create ns "${NAMESPACE}" || {
        log "ERROR: Failed to create namespace ${NAMESPACE}."
        exit 1
    }
}

apply_manifest() {
    log "Checking for ${MANIFEST_FILE}"
    if [ ! -f "${MANIFEST_FILE}" ]; then
        log "ERROR: ${MANIFEST_FILE} not found."
        exit 1
    fi
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

cleanup() {
    log "Cleaning up temporary files (if any)"
    # Add cleanup for any temporary files created during execution
    # e.g., rm -f temporary_config.yaml
}

rollback() {
    log "Rolling back deployment"
    "${KUBECTL}" delete -f "${MANIFEST_FILE}" --ignore-not-found
}

install_traefik_crds() {
    log "Installing Traefik CRDs"
    "${KUBECTL}" apply -f https://raw.githubusercontent.com/traefik/traefik/v2.10/traefik.crds.yaml || {
        log "ERROR: Failed to install Traefik CRDs."
        exit 1
    }
}
cert_manager() {
    log "Installing cert-manager"
    "${KUBECTL}" apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.1/cert-manager.yaml || {
        log "ERROR: Failed to install cert-manager."
        exit 1
    }
}

main() {
    log "Starting Keycloak deployment process at $(date '+%Y-%m-%d %H:%M:%S')"
    check_requirements
    install_traefik_crds
    cert_manager
    ensure_namespace
    apply_manifest
    verify_deployment
    #rollback
    log "Deployment completed successfully at $(date '+%Y-%m-%d %H:%M:%S')"
}

#trap rollback ERR
trap cleanup EXIT

main && "${KUBECTL}" cluster-info >/dev/null 2>&1 || {
    log "ERROR: Kubernetes cluster is not accessible."
    exit 1
}