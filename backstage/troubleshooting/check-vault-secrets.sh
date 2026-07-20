#!/usr/bin/env bash
# Verify every secret the portal needs is present and readable with the
# PORTAL'S OWN token (not root) — exactly what entrypoint.sh does at boot.
# Diagnoses "entrypoint: FAIL no Vault token appeared / could not read ..."
set -uo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"

echo "==> vault status"
"$RUNTIME" exec backstage-vault vault status 2>/dev/null | grep -E 'Initialized|Sealed' || { echo "FAIL: vault unreachable"; exit 1; }

echo "==> portal-state tokens"
for f in backstage-token boundary-vault-token vault-init.json oidc-client-secret boundary-ids.env; do
  if "$RUNTIME" run --rm --user root -v backstage_portal-state:/s:ro localhost/vault:2.0.3 \
      test -s "/s/$f" 2>/dev/null; then echo "    $f: present"
  else echo "    $f: MISSING (rerun the matching setup one-shot)"; fi
done

PT=$("$RUNTIME" run --rm --user root -v backstage_portal-state:/s:ro localhost/vault:2.0.3 \
  cat /s/backstage-token 2>/dev/null || true)
[ -n "$PT" ] || { echo "FAIL: no portal token — podman start -a backstage-vault-setup"; exit 1; }

echo "==> reads with the portal's scoped token (what the entrypoint does)"
for path in "database/static-creds/backstage-portal:username" \
            "secret/gitea/portal:username" \
            "secret/oidc/portal:client_secret"; do
  P=${path%%:*}; F=${path##*:}
  if [ "$(echo "$P" | grep -c '^secret/')" -gt 0 ]; then CMD="vault kv get -field=$F $P"; else CMD="vault read -field=$F $P"; fi
  if OUT=$("$RUNTIME" exec -e VAULT_TOKEN="$PT" backstage-vault $CMD 2>&1); then
    case "$F" in username) echo "    $P: ok ($F=$OUT)";; *) echo "    $P: ok";; esac
  else
    echo "    $P: FAIL -> $OUT"
    echo "      (token expired? mint a fresh one: podman start -a backstage-vault-setup"
    echo "       after removing the stale file from the portal-state volume)"
  fi
done

echo "==> token TTL"
"$RUNTIME" exec -e VAULT_TOKEN="$PT" backstage-vault vault token lookup 2>/dev/null \
  | grep -E '^ttl|^period' || echo "    lookup failed (expired token)"
echo "check-vault-secrets: DONE"
