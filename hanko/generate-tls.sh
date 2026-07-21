#!/bin/bash
set -e

# Generate self-signed TLS certificates for local development
DOMAIN="hanko.your-domain.com"
CERT_DIR="./tls"
SECRET_NAME="hanko-tls"
NAMESPACE="hanko"

# Create certificate directory
mkdir -p "$CERT_DIR"

# Generate CA
openssl genrsa -out "$CERT_DIR/ca.key" 4096
openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha256 -days 3650 \
    -out "$CERT_DIR/ca.crt" -subj "/CN=Hanko CA"

# Generate server certificate
# SANs include the compose service names so in-cluster clients can use
# verify-full against "postgresql" etc.
SAN="subjectAltName=DNS:$DOMAIN,DNS:localhost,DNS:postgresql,DNS:hanko,DNS:mailslurper,IP:127.0.0.1"

openssl genrsa -out "$CERT_DIR/tls.key" 2048
openssl req -new -key "$CERT_DIR/tls.key" -out "$CERT_DIR/tls.csr" \
    -subj "/CN=$DOMAIN" \
    -addext "$SAN"

openssl x509 -req -in "$CERT_DIR/tls.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial -out "$CERT_DIR/tls.crt" -days 365 -sha256 \
    -extfile <(echo "$SAN")

# Create Kubernetes secret (only when a cluster is reachable)
if command -v kubectl >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
    kubectl create secret tls "$SECRET_NAME" --cert="$CERT_DIR/tls.crt" --key="$CERT_DIR/tls.key" -n "$NAMESPACE" || \
        kubectl replace secret tls "$SECRET_NAME" --cert="$CERT_DIR/tls.crt" --key="$CERT_DIR/tls.key" -n "$NAMESPACE"
fi

echo "TLS certificates generated in $CERT_DIR and stored in Kubernetes secret $SECRET_NAME in namespace $NAMESPACE"