#!/usr/bin/env bash
# Self-signed certificate for the Traefik dashboard.
#
#   ./gen-traefik-cert.sh
#
# A subjectAltName is mandatory. Every current browser ignores the Common Name
# and matches only against SAN, so a CN-only certificate fails to validate even
# when the name is right.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${HERE}/secrets"
DAYS="${CERT_DAYS:-365}"
DOMAIN="${CERT_DOMAIN:-podman.localhost}"

mkdir -p "$OUT"

openssl req -x509 -nodes -days "$DAYS" -newkey rsa:4096 \
    -keyout "${OUT}/traefik.key" -out "${OUT}/traefik.crt" \
    -subj "/CN=*.${DOMAIN}" \
    -addext "subjectAltName=DNS:*.${DOMAIN},DNS:${DOMAIN}" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth"

chmod 600 "${OUT}/traefik.key"
chmod 644 "${OUT}/traefik.crt"

echo "wrote ${OUT}/traefik.crt and traefik.key, valid ${DAYS} days"
openssl x509 -in "${OUT}/traefik.crt" -noout -ext subjectAltName
