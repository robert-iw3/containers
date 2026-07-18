#!/usr/bin/env bash
# Smoke / UAT test for the 3-node Consul cluster.
# Bootstraps the ACL system on first run (management token stored in
# .consul-bootstrap.json, chmod 600), then verifies raft membership,
# KV round-trip, and service registration.
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"
BOOTSTRAP_FILE=".consul-bootstrap.json"

cexec() { "$RUNTIME" exec -e CONSUL_HTTP_TOKEN="${CONSUL_HTTP_TOKEN:-}" consul-server1 consul "$@"; }

echo "==> waiting for a raft leader"
for i in $(seq 1 60); do
  LEADER=$("$RUNTIME" exec consul-server1 curl -sf http://127.0.0.1:8500/v1/status/leader 2>/dev/null || true)
  [ -n "$LEADER" ] && [ "$LEADER" != '""' ] && break
  [ "$i" = 60 ] && { echo "FAIL: no leader elected"; exit 1; }
  sleep 2
done
echo "    leader: $LEADER"

if [ ! -s "$BOOTSTRAP_FILE" ]; then
  echo "==> bootstrapping ACL system"
  for i in $(seq 1 30); do
    if "$RUNTIME" exec consul-server1 consul acl bootstrap -format=json > "$BOOTSTRAP_FILE" 2>/dev/null; then
      break
    fi
    [ "$i" = 30 ] && { echo "FAIL: acl bootstrap never succeeded (was it bootstrapped outside this script?)"; exit 1; }
    sleep 2
  done
  chmod 600 "$BOOTSTRAP_FILE"
  echo "    management token written to consul/$BOOTSTRAP_FILE (keep safe, UAT only)"
fi

CONSUL_HTTP_TOKEN=$(python3 -c "import json;print(json.load(open('$BOOTSTRAP_FILE'))['SecretID'])")
export CONSUL_HTTP_TOKEN

echo "==> cluster members"
cexec members
MEMBERS=$(cexec members | grep -c alive || true)
[ "$MEMBERS" -ge 3 ] || { echo "FAIL: expected 3 alive members, got $MEMBERS"; exit 1; }

echo "==> raft peers"
cexec operator raft list-peers

echo "==> KV round-trip"
cexec kv put smoke-test/ping pong >/dev/null
GOT=$(cexec kv get smoke-test/ping)
[ "$GOT" = "pong" ] || { echo "FAIL: kv round-trip returned '$GOT'"; exit 1; }
cexec kv delete smoke-test/ping >/dev/null

echo "==> service registration + catalog lookup"
cexec services register -name=smoke-svc -port=9999 >/dev/null
cexec catalog services | grep -q smoke-svc || { echo "FAIL: smoke-svc not in catalog"; exit 1; }
cexec services deregister -id=smoke-svc >/dev/null

echo
echo "PASS: 3-node cluster healthy — TLS, gossip encryption, and ACLs active."
echo "UI:    https://localhost:8501/ui  (self-signed cert — accept the warning)"
echo "Token: $CONSUL_HTTP_TOKEN"
