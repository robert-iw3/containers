#!/usr/bin/env bash
# Smoke / UAT test for the standalone Vault stack.
# Initializes Vault on first run (keys stored in .vault-init.json, chmod 600),
# unseals if needed, then exercises the KV engine end to end.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE="${COMPOSE:-podman-compose}"
RUNTIME="${RUNTIME:-podman}"
INIT_FILE=".vault-init.json"

vexec() { "$RUNTIME" exec -e VAULT_TOKEN="${VAULT_TOKEN:-}" vault vault "$@"; }

echo "==> waiting for Vault API to respond"
for i in $(seq 1 30); do
  if "$RUNTIME" exec vault curl -sf --cacert /certs/vault-ca.crt.pem \
      "https://127.0.0.1:8200/v1/sys/health?uninitcode=200&sealedcode=200" >/dev/null 2>&1; then
    break
  fi
  [ "$i" = 30 ] && { echo "FAIL: Vault API never came up"; exit 1; }
  sleep 2
done

status_json() { vexec status -format=json 2>/dev/null || true; }

if [ "$(status_json | grep -o '"initialized": [a-z]*' | awk '{print $2}')" != "true" ]; then
  echo "==> initializing Vault (1 key share, threshold 1 — UAT only)"
  "$RUNTIME" exec vault vault operator init -key-shares=1 -key-threshold=1 -format=json > "$INIT_FILE"
  chmod 600 "$INIT_FILE"
  echo "    unseal key + root token written to vault/$INIT_FILE (keep safe, UAT only)"
fi

UNSEAL_KEY=$(python3 -c "import json;print(json.load(open('$INIT_FILE'))['unseal_keys_b64'][0])")
VAULT_TOKEN=$(python3 -c "import json;print(json.load(open('$INIT_FILE'))['root_token'])")
export VAULT_TOKEN

if [ "$(status_json | grep -o '"sealed": [a-z]*' | awk '{print $2}')" = "true" ]; then
  echo "==> unsealing"
  vexec operator unseal "$UNSEAL_KEY" >/dev/null
fi

echo "==> vault status"
vexec status

echo "==> enabling kv-v2 at secret/ (idempotent)"
vexec secrets enable -path=secret kv-v2 2>/dev/null || echo "    already enabled"

echo "==> write/read round-trip"
vexec kv put secret/smoke-test ping=pong ts="$(date -u +%FT%TZ)" >/dev/null
GOT=$(vexec kv get -field=ping secret/smoke-test)
[ "$GOT" = "pong" ] || { echo "FAIL: kv round-trip returned '$GOT'"; exit 1; }

echo "==> audit device (file) enabled (idempotent)"
vexec audit enable file file_path=/vault/logs/audit.log 2>/dev/null || echo "    already enabled"

echo
echo "PASS: Vault is initialized, unsealed, and serving KV secrets."
echo "UI:    https://localhost:8200/ui  (self-signed cert — accept the warning)"
echo "Token: $(python3 -c "import json;print(json.load(open('$INIT_FILE'))['root_token'])")"
