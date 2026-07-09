#!/usr/bin/env bash
# Generate a self-signed TLS cert+key for the Airflow api-server (UI/login + the
# internal execution API). SANs cover the compose service name, localhost, and the
# k8s service DNS so both the browser and the internal components can verify it.
#
# For production, replace this with a cert from your CA / cert-manager / Let's Encrypt.
set -euo pipefail

CERT_DIR="${1:-$(dirname "$0")/../certs}"
mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout "$CERT_DIR/tls.key" \
  -out "$CERT_DIR/tls.crt" \
  -subj "/CN=airflow-apiserver" \
  -addext "subjectAltName=DNS:airflow-apiserver,DNS:airflow-apiserver.airflow.svc.cluster.local,DNS:localhost,IP:127.0.0.1"

chmod 644 "$CERT_DIR/tls.crt"
chmod 640 "$CERT_DIR/tls.key"
echo "wrote $CERT_DIR/tls.crt and $CERT_DIR/tls.key"
