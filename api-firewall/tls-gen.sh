#!/bin/sh
# Generate a local CA and a server certificate for API Firewall TLS
# termination into ./certs. Uses config/ca-csr.conf and config/api-fw-csr.conf;
# edit the SANs there to match your hostname first. Idempotent: refuses to
# overwrite existing certs unless -f is given.
#
# For production, prefer certificates from your real PKI / ACME and simply
# drop them in ./certs as api-fw.crt.pem + api-fw.key.pem.
set -eu

cd "$(dirname "$0")"

CERTS_DIR=certs
CA_DAYS=730
CERT_DAYS=365

if [ -f "$CERTS_DIR/api-fw.crt.pem" ] && [ "${1:-}" != "-f" ]; then
    echo "certs already exist in $CERTS_DIR/ (use -f to regenerate)" >&2
    exit 1
fi

# World-traversable dir / world-readable files so the container user
# (uid 65535, remapped under rootless podman) can read them. This local CA
# is for testing TLS wiring; production should mount real certificates with
# proper ownership (or use your orchestrator's secrets mechanism).
mkdir -p "$CERTS_DIR"
chmod 755 "$CERTS_DIR"

echo "--> Generating CA..."
openssl genrsa -out "$CERTS_DIR/ca.key.pem" 4096
openssl req -new -x509 -days "$CA_DAYS" -key "$CERTS_DIR/ca.key.pem" \
    -config config/ca-csr.conf -out "$CERTS_DIR/ca.crt.pem"

echo "--> Generating server certificate..."
openssl genrsa -out "$CERTS_DIR/api-fw.key.pem" 4096
openssl req -new -key "$CERTS_DIR/api-fw.key.pem" \
    -out "$CERTS_DIR/api-fw.csr" -config config/api-fw-csr.conf
openssl x509 -req -in "$CERTS_DIR/api-fw.csr" \
    -CA "$CERTS_DIR/ca.crt.pem" -CAkey "$CERTS_DIR/ca.key.pem" \
    -CAcreateserial -sha512 -days "$CERT_DAYS" \
    -extfile config/api-fw-csr.conf -extensions req_ext \
    -out "$CERTS_DIR/api-fw.crt.pem"

rm -f "$CERTS_DIR/api-fw.csr" "$CERTS_DIR"/*.srl
# Key files must stay readable by the container user (uid 65535).
chmod 644 "$CERTS_DIR"/*.crt.pem
chmod 644 "$CERTS_DIR"/*.key.pem

echo "--> Done. Enable in .env:"
echo "      APIFW_URL=https://0.0.0.0:8080"
