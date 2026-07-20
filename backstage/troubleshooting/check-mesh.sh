#!/usr/bin/env bash
# Verify the Consul Connect datapath the portal depends on, and optionally
# repair it. Diagnoses the failure mode where recreated core containers
# (consul/postgres) leave the long-running sidecars holding dead state —
# symptom: portal logs "Connection terminated unexpectedly" against the DB.
#
#   ./troubleshooting/check-mesh.sh            # diagnose only
#   ./troubleshooting/check-mesh.sh --repair   # also bounce the sidecars
set -uo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
REPAIR="${1:-}"

rc=0

echo "==> sidecar containers"
for c in backstage-postgres-sidecar backstage-gitea-sidecar backstage-portal-sidecar; do
  ST=$("$RUNTIME" inspect --format '{{.State.Status}}' "$c" 2>/dev/null || echo missing)
  echo "    $c: $ST"
  [ "$ST" = "running" ] || rc=1
done

echo "==> sidecar registrations on the consul agent"
SVCS=$("$RUNTIME" exec backstage-consul curl -sf --cacert /portal-certs/ca.crt \
  https://127.0.0.1:8501/v1/agent/services 2>/dev/null || true)
for s in postgres-sidecar-proxy gitea-sidecar-proxy backstage-sidecar-proxy; do
  if [ "$(echo "$SVCS" | grep -c "$s")" -gt 0 ]; then echo "    $s: registered"
  else echo "    $s: MISSING"; rc=1; fi
done

echo "==> egress upstream listeners (portal -> mesh)"
for probe in "backstage-sidecar 20001 postgres" "backstage-sidecar 20002 gitea"; do
  set -- $probe
  if "$RUNTIME" exec backstage-consul sh -c "nc -z -w3 $1 $2" 2>/dev/null; then
    echo "    $1:$2 ($3): TCP OK"
  else
    echo "    $1:$2 ($3): UNREACHABLE"; rc=1
  fi
done

echo "==> end-to-end: gitea catalog file through the mesh (mTLS + TLS)"
CODE=$("$RUNTIME" exec backstage-portal-a curl -s --cacert /portal-certs/ca.crt -o /dev/null \
  -w '%{http_code}' https://backstage-sidecar:20002/devteam/sample-service/raw/branch/main/catalog-info.yaml 2>/dev/null || echo down)
echo "    fetch via backstage-sidecar:20002 -> HTTP $CODE"
[ "$CODE" = "200" ] || rc=1

if [ "$rc" -ne 0 ] && [ "$REPAIR" = "--repair" ]; then
  echo "==> repairing: restarting sidecars (they re-register + re-resolve)"
  "$RUNTIME" restart backstage-postgres-sidecar backstage-gitea-sidecar backstage-portal-sidecar >/dev/null
  for i in $(seq 1 20); do
    "$RUNTIME" exec backstage-consul sh -c 'nc -z -w3 backstage-sidecar 20001 && nc -z -w3 backstage-sidecar 20002' 2>/dev/null \
      && { echo "    mesh upstreams recovered"; rc=0; break; }
    sleep 3
  done
  [ "$rc" -ne 0 ] && echo "    still broken — check consul + service registrations above"
fi

[ "$rc" -eq 0 ] && echo "check-mesh: OK" || echo "check-mesh: PROBLEMS FOUND"
exit "$rc"
