#!/usr/bin/env bash
# One-screen health overview of the whole portal stack: container states,
# health endpoints, consul catalog + intentions, vault seal status, boundary
# ops health, portal readiness per replica.
set -uo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"

echo "== containers"
"$RUNTIME" ps -a --format '{{.Names}}\t{{.Status}}' | grep backstage | sort | column -t -s$'\t'

echo
echo "== consul (leader / services / intentions)"
LEADER=$("$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt \
  https://127.0.0.1:8501/v1/status/leader 2>/dev/null || echo "UNREACHABLE")
echo "leader: $LEADER"
"$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt \
  https://127.0.0.1:8501/v1/catalog/services 2>/dev/null || echo "catalog unreachable"
echo
for pair in "backstage postgres" "backstage gitea" "gitea postgres"; do
  set -- $pair
  OUT=$("$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt \
    "https://127.0.0.1:8501/v1/connect/intentions/check?source=$1&destination=$2" 2>/dev/null || echo '?')
  echo "intention $1 -> $2: $OUT"
done

echo
echo "== vault"
"$RUNTIME" exec backstage-vault vault status 2>/dev/null | grep -E 'Initialized|Sealed|HA Mode' || echo "vault unreachable"

echo
echo "== boundary ops"
"$RUNTIME" exec backstage-boundary wget -q -O- --ca-certificate=/portal-certs/ca.crt \
  https://127.0.0.1:9203/health 2>/dev/null && echo " (ok)" || echo "ops endpoint unreachable"

echo
echo "== portal replicas (readiness) + proxy routing"
for c in backstage-portal-a backstage-portal-b; do
  CODE=$("$RUNTIME" exec "$c" curl -s -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:7007/.backstage/health/v1/readiness 2>/dev/null || echo down)
  echo "$c readiness: $CODE"
done
"$RUNTIME" exec backstage-portal-a curl -s --cacert /portal-certs/ca.crt -D - -o /dev/null \
  https://portal-proxy:8443/ 2>/dev/null | tr -d '\r' | grep -iE '^HTTP|^x-portal-deployment' \
  || echo "proxy unreachable"

echo
echo "== gitea / keycloak"
"$RUNTIME" exec backstage-gitea curl -sf --cacert /portal-certs/ca.crt \
  https://127.0.0.1:3000/api/healthz >/dev/null 2>&1 && echo "gitea: ok" || echo "gitea: DOWN"
"$RUNTIME" exec backstage-keycloak bash -c 'exec 3<>/dev/tcp/127.0.0.1/9000' 2>/dev/null \
  && echo "keycloak mgmt: ok" || echo "keycloak mgmt: DOWN"
