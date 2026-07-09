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
openssl genrsa -out "$CERT_DIR/tls.key" 2048
openssl req -new -key "$CERT_DIR/tls.key" -out "$CERT_DIR/tls.csr" \
    -subj "/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"

openssl x509 -req -in "$CERT_DIR/tls.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial -out "$CERT_DIR/tls.crt" -days 365 -sha256 \
    -extfile <(echo "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1")

# Create Kubernetes secret
kubectl create secret tls "$SECRET_NAME" --cert="$CERT_DIR/tls.crt" --key="$CERT_DIR/tls.key" -n "$NAMESPACE" || \
    kubectl replace secret tls "$SECRET_NAME" --cert="$CERT_DIR/tls.crt" --key="$CERT_DIR/tls.key" -n "$NAMESPACE"

echo "TLS certificates generated in $CERT_DIR and stored in Kubernetes secret $SECRET_NAME in namespace $NAMESPACE"