#!/usr/bin/env bash
# Host-run one-shot: wait for keycloak-setup to finish, then push the OIDC
# client secret it generated into Vault kv (secret/oidc/portal) where the
# portal reads it at boot. Split from keycloak-setup because the Keycloak
# image carries no Vault CLI.
set -euo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"

echo "==> waiting for keycloak-setup to finish"
for i in $(seq 1 120); do
  [ "$("$RUNTIME" logs backstage-keycloak-setup 2>&1 | grep -c 'keycloak-setup: DONE')" -gt 0 ] && break
  [ "$("$RUNTIME" logs backstage-keycloak-setup 2>&1 | grep -c '^FAIL')" -gt 0 ] \
    && { "$RUNTIME" logs backstage-keycloak-setup | tail -5; echo "FAIL: keycloak-setup failed"; exit 1; }
  [ "$i" = 120 ] && { "$RUNTIME" logs backstage-keycloak-setup | tail -10; echo "FAIL: keycloak-setup never finished"; exit 1; }
  sleep 2
done

echo "==> pushing OIDC client secret into Vault kv (secret/oidc/portal)"
ROOT_TOKEN=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  python3 -c "import json;print(json.load(open('/portal-state/vault-init.json'))['root_token'])")
OIDC_SECRET=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/portal-state:ro localhost/vault:2.0.3 \
  cat /portal-state/oidc-client-secret)
"$RUNTIME" exec -e VAULT_TOKEN="$ROOT_TOKEN" -e OS="$OIDC_SECRET" backstage-vault \
  sh -c 'vault kv put secret/oidc/portal client_secret="$OS"' >/dev/null
echo "    stored"

echo "idp-setup: DONE"
