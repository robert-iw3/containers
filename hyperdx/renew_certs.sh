#!/bin/bash

CERT_TYPE="$1"
DOMAIN="$2"
EMAIL="$3"
OUT_DIR="/opt/hyperdx/docker/nginx/ssl"

case "$CERT_TYPE" in
    letsencrypt)
        certbot renew
        cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$OUT_DIR/"
        cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$OUT_DIR/"
        docker compose -f /opt/hyperdx/docker-compose.yml restart nginx
        ;;
    self-signed)
        /opt/hyperdx/certs.sh --type self-signed --domain "$DOMAIN" --out-dir "$OUT_DIR"
        docker compose -f /opt/hyperdx/docker-compose.yml restart nginx
        ;;
    *)
        echo "Unsupported cert_type for renewal: $CERT_TYPE"
        exit 1
        ;;
esac