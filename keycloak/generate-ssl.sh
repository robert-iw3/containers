#!/bin/bash
set -euo pipefail

# Configuration
CERT_DIR="/home/keycloak/certs"
CERT_FILE="${CERT_DIR}/keycloak.io.pem"
KEY_FILE="${CERT_DIR}/keycloak.io.key.pem"
DAYS_VALID=365
KEY_SIZE=4096
SUBJ="/C=US/ST=State/L=City/O=Organization/OU=Unit/CN=keycloak.io"

mkdir -p "${CERT_DIR}"
openssl req -x509 -newkey rsa:${KEY_SIZE} -keyout "${KEY_FILE}" -out "${CERT_FILE}" \
    -days ${DAYS_VALID} -nodes -subj "${SUBJ}"

chown keycloak:keycloak "${CERT_DIR}" "${CERT_FILE}" "${KEY_FILE}"
chmod 600 "${CERT_FILE}" "${KEY_FILE}"