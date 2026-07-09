#!/bin/bash

TYPE=""
DOMAIN=""
EMAIL=""
OUT_DIR="./docker/nginx/ssl"
DAYS=365
CA_CNF="ca.cnf"
CSR_CNF="csr.cnf"

while [[ $# -gt 0 ]]; do
    case $1 in
        --type) TYPE="$2"; shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --email) EMAIL="$2"; shift 2 ;;
        --out-dir) OUT_DIR="$2"; shift 2 ;;
        --days) DAYS="$2"; shift 2 ;;
        *) echo "Unknown option $1"; exit 1 ;;
    esac
done

if [ -z "$TYPE" ] || [ -z "$DOMAIN" ]; then
    echo "Usage: $0 --type [self-signed|letsencrypt|csr] --domain example.com [--email email] [--out-dir ./ssl] [--days 365]"
    exit 1
fi

mkdir -p "$OUT_DIR"

case "$TYPE" in
    self-signed)
        openssl genrsa -out "$OUT_DIR/ca.key" 4096
        openssl req -x509 -new -nodes -key "$OUT_DIR/ca.key" -sha256 -days "$DAYS" -out "$OUT_DIR/ca.crt" -config "$CA_CNF" -subj "/CN=Self-Signed-CA"
        openssl genrsa -out "$OUT_DIR/server.key" 2048
        openssl req -new -key "$OUT_DIR/server.key" -out "$OUT_DIR/server.csr" -config "$CSR_CNF" -subj "/CN=$DOMAIN"
        openssl x509 -req -in "$OUT_DIR/server.csr" -CA "$OUT_DIR/ca.crt" -CAkey "$OUT_DIR/ca.key" -CAcreateserial -out "$OUT_DIR/server.crt" -days "$DAYS" -sha256
        cat "$OUT_DIR/server.crt" "$OUT_DIR/ca.crt" > "$OUT_DIR/fullchain.pem"
        cp "$OUT_DIR/server.key" "$OUT_DIR/privkey.pem"
        echo "Self-signed certs generated in $OUT_DIR"
        ;;

    letsencrypt)
        if [ -z "$EMAIL" ]; then
            echo "Email required for Let's Encrypt"
            exit 1
        fi
        certbot certonly --standalone -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
        cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$OUT_DIR/"
        cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$OUT_DIR/"
        echo "Let's Encrypt certs generated and copied to $OUT_DIR"
        ;;

    csr)
        openssl genrsa -out "$OUT_DIR/server.key" 2048
        openssl req -new -key "$OUT_DIR/server.key" -out "$OUT_DIR/server.csr" -config "$CSR_CNF" -subj "/CN=$DOMAIN"
        echo "CSR and key generated in $OUT_DIR. Submit server.csr to CA."
        ;;

    *)
        echo "Invalid type: $TYPE"
        exit 1
        ;;
esac