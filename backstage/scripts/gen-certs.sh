#!/usr/bin/env bash
# One-shot: mint the stack's demo CA and per-service TLS certs into the
# shared portal-certs volume. Every published or internal HTTP endpoint
# serves TLS from this CA (Vault keeps its own CA from ../vault tooling).
# Idempotent: skips generation when the CA already exists.
set -euo pipefail

CERTS=/portal-certs
DAYS=825

if [ -s "$CERTS/ca.crt" ]; then
  echo "gen-certs: CA already present, nothing to do"
  exit 0
fi

echo "==> generating stack CA"
openssl genrsa -out "$CERTS/ca.key" 4096 2>/dev/null
openssl req -x509 -new -key "$CERTS/ca.key" -sha256 -days $DAYS \
  -subj "/CN=backstage-portal-demo-ca" -out "$CERTS/ca.crt"

issue() { # issue <name> <san-list>
  local name=$1 sans=$2
  echo "==> issuing $name ($sans)"
  openssl genrsa -out "$CERTS/$name.key" 2048 2>/dev/null
  openssl req -new -key "$CERTS/$name.key" -subj "/CN=$name" \
    -out "$CERTS/$name.csr"
  openssl x509 -req -in "$CERTS/$name.csr" -CA "$CERTS/ca.crt" \
    -CAkey "$CERTS/ca.key" -CAcreateserial -days $DAYS -sha256 \
    -extfile <(printf "subjectAltName=%s\nextendedKeyUsage=serverAuth,clientAuth" "$sans") \
    -out "$CERTS/$name.crt" 2>/dev/null
  rm -f "$CERTS/$name.csr"
}

issue portal-proxy "DNS:portal-proxy,DNS:localhost,IP:127.0.0.1"
# gitea + postgres are reached through the portal's egress sidecar, so the
# client-facing hostname is backstage-sidecar — it must be in the SANs
issue gitea        "DNS:gitea,DNS:backstage-sidecar,DNS:localhost,IP:127.0.0.1"
issue postgres     "DNS:postgres,DNS:backstage-sidecar,DNS:localhost,IP:127.0.0.1"
issue boundary-db  "DNS:boundary-db,DNS:localhost,IP:127.0.0.1"
issue keycloak     "DNS:keycloak,DNS:localhost,IP:127.0.0.1"
issue consul       "DNS:consul,DNS:localhost,IP:127.0.0.1"
issue boundary     "DNS:boundary,DNS:localhost,IP:127.0.0.1"

# demo volume: keys must be readable by each service's container user
# (nginx root, gitea 1000, postgres wrappers re-copy with strict modes)
chmod 644 "$CERTS"/*.crt "$CERTS"/*.key
chmod 600 "$CERTS/ca.key"

echo "gen-certs: DONE"
ls -l "$CERTS"
