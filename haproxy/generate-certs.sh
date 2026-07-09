#!/bin/bash
set -e

CONFIG_DIR="config"
CERT_DIR="/usr/local/etc/haproxy/certs"
DOMAIN="haproxy.example.com"
EMAIL="admin@example.com"

# Ensure certificate directory exists
mkdir -p "$CERT_DIR"

# Generate self-signed CA and server certificates
if [ ! -f "$CERT_DIR/ca.crt" ]; then
  echo "Generating self-signed CA certificate..."
  openssl genrsa -out "$CERT_DIR/ca.key" 4096
  openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha512 -days 3650 -out "$CERT_DIR/ca.crt" -config "$CONFIG_DIR/ca-csr.conf"
fi

if [ ! -f "$CERT_DIR/server.crt" ]; then
  echo "Generating self-signed server certificate..."
  openssl genrsa -out "$CERT_DIR/server.key" 2048
  openssl req -new -key "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" -config "$CONFIG_DIR/server-csr.conf"
  openssl x509 -req -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/server.crt" -days 365 -sha512 -extensions req_ext -extfile "$CONFIG_DIR/server-csr.conf"
  cat "$CERT_DIR/server.crt" "$CERT_DIR/server.key" > "$CERT_DIR/haproxy.pem"
fi

# Attempt to get Let's Encrypt certificate
if command -v certbot >/dev/null 2>&1; then
  echo "Attempting to obtain Let's Encrypt certificate..."
  certbot certonly --standalone -d "$DOMAIN" --email "$EMAIL" --non-interactive --agree-tos --http-01-port 8088 || {
    echo "Let's Encrypt certificate issuance failed, falling back to self-signed certificate."
    exit 0
  }
  cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/haproxy.pem"
  cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/server.key"
else
  echo "Certbot not found, using self-signed certificate."
fi

chmod 600 "$CERT_DIR/haproxy.pem" "$CERT_DIR/server.key"
chown 99:99 "$CERT_DIR/haproxy.pem" "$CERT_DIR/server.key"