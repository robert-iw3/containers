#!/usr/bin/env bash
# Explain WHY a portal replica is unhealthy: classifies the newest boot's
# errors against every failure signature met in practice and prints the
# matching fix.
#
#   ./troubleshooting/diagnose-portal.sh [backstage-portal-a|backstage-portal-b]
set -uo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
C="${1:-backstage-portal-a}"

ST=$("$RUNTIME" inspect --format '{{.State.Status}} (health: {{.State.Health.Status}})' "$C" 2>/dev/null || echo missing)
echo "==> $C: $ST"
[ "$ST" = "missing" ] && { echo "    container does not exist — run ./run_portal.sh"; exit 1; }

CODE=$("$RUNTIME" exec "$C" curl -s -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:7007/.backstage/health/v1/readiness 2>/dev/null || echo down)
echo "    readiness: $CODE"
[ "$CODE" = "200" ] && { echo "diagnose-portal: healthy — nothing to do"; exit 0; }

LOGS=$("$RUNTIME" logs --tail 400 "$C" 2>&1)

hits() { echo "$LOGS" | grep -c "$1"; }

echo
echo "==> failure signatures in the recent log"
FOUND=0

if [ "$(hits 'no Vault token appeared')" -gt 0 ]; then
  FOUND=1
  echo "  * entrypoint waiting for Vault token"
  echo "    -> vault-setup never wrote /portal-state/backstage-token"
  echo "    -> run: podman start -a backstage-vault-setup ; then ./troubleshooting/check-vault-secrets.sh"
fi
if [ "$(hits 'could not read secret/data/gitea/portal')" -gt 0 ] || [ "$(hits 'could not read secret/data/oidc/portal')" -gt 0 ]; then
  FOUND=1
  echo "  * entrypoint timed out on a kv secret (gitea or oidc)"
  echo "    -> provisioning did not run before the portal booted"
  echo "    -> run: ./scripts/gitea-setup.sh && ./scripts/idp-setup.sh ; then podman start $C"
fi
if [ "$(hits 'Migration table is already locked')" -gt 0 ]; then
  FOUND=1
  echo "  * knex MigrationLocked"
  echo "    -> run: ./troubleshooting/fix-migration-locks.sh"
fi
if [ "$(hits 'already exists')" -gt 0 ] && [ "$(hits 'knex_migrations')" -gt 0 ]; then
  FOUND=1
  echo "  * migration DDL race (create table ... already exists)"
  echo "    -> both replicas migrated a fresh DB at once; run: ./troubleshooting/fix-migration-locks.sh"
fi
if [ "$(hits 'Connection terminated unexpectedly')" -gt 0 ]; then
  FOUND=1
  echo "  * DB connections dying mid-flight"
  echo "    -> sidecar/mesh state is stale (core containers recreated?)"
  echo "    -> run: ./troubleshooting/check-mesh.sh --repair ; then podman restart $C"
fi
if [ "$(hits 'password authentication failed')" -gt 0 ]; then
  FOUND=1
  echo "  * DB auth failure"
  echo "    -> static-cred/bootstrap mismatch; verify: ./troubleshooting/check-vault-secrets.sh"
fi
if [ "$(hits 'self-signed certificate\|unable to verify the first certificate\|certificate')" -gt 0 ] \
   && [ "$(hits 'FetchError\|UNABLE_TO')" -gt 0 ]; then
  FOUND=1
  echo "  * TLS trust failure on an outbound call"
  echo "    -> NODE_EXTRA_CA_CERTS must point at the stack CA and target certs need the backstage-sidecar SAN"
fi

if [ "$FOUND" = 0 ]; then
  echo "  (no known signature — last errors below)"
  echo "$LOGS" | grep -iE '"level":"error"|FAIL' | tail -6 | cut -c1-220 | sed 's/^/    /'
fi
