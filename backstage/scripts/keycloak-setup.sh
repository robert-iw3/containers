#!/usr/bin/env bash
# One-shot: provision the portal's identity realm in Keycloak.
#   realm "portal", confidential OIDC client "backstage-portal" (redirect to
#   the Boundary session URL), demo user portal-dev.
# The generated client secret is written to /portal-state; the host-side
# idp-setup.sh pushes it into Vault kv (this image has no Vault CLI).
# Idempotent via kcadm create-or-update semantics + state marker.
set -euo pipefail

KC=/opt/keycloak/bin/kcadm.sh
STATE=/portal-state
SERVER=https://keycloak:8443
REALM=portal
CLIENT_ID=backstage-portal
REDIRECT="${PORTAL_BASE_URL:-https://127.0.0.1:27007}/api/auth/oidc/handler/frame"

echo "==> trusting the stack CA (kcadm truststore)"
rm -f /tmp/trust.jks
keytool -importcert -noprompt -alias portal-ca \
  -file /portal-certs/ca.crt -keystore /tmp/trust.jks -storepass changeit >/dev/null 2>&1
"$KC" config truststore --trustpass changeit /tmp/trust.jks

echo "==> waiting for Keycloak admin API"
for i in $(seq 1 90); do
  "$KC" config credentials --server "$SERVER" --realm master \
    --user admin --password "$KC_ADMIN_PASSWORD" >/dev/null 2>&1 && break
  [ "$i" = 90 ] && { echo "FAIL: keycloak admin login never succeeded"; exit 1; }
  sleep 2
done

echo "==> realm $REALM"
"$KC" create realms -s realm=$REALM -s enabled=true 2>/dev/null \
  || echo "    realm already exists"

echo "==> client $CLIENT_ID"
if [ ! -s "$STATE/oidc-client-secret" ]; then
  # secret survives re-runs via portal-state; Vault gets the same value
  tr -dc 'a-f0-9' < /dev/urandom | head -c 48 > "$STATE/oidc-client-secret"
  chmod 600 "$STATE/oidc-client-secret"
fi
SECRET=$(cat "$STATE/oidc-client-secret")

# sed -n 1p (not head) — head's early pipe close SIGPIPEs kcadm under pipefail
CID=$("$KC" get clients -r $REALM -q clientId=$CLIENT_ID --fields id --format csv --noquotes 2>/dev/null | sed -n 1p || true)
if [ -z "$CID" ]; then
  "$KC" create clients -r $REALM \
    -s clientId=$CLIENT_ID \
    -s enabled=true \
    -s publicClient=false \
    -s standardFlowEnabled=true \
    -s directAccessGrantsEnabled=true \
    -s "secret=$SECRET" \
    -s "redirectUris=[\"$REDIRECT\"]" \
    -s "webOrigins=[\"${PORTAL_BASE_URL:-https://127.0.0.1:27007}\"]"
  echo "    client created"
else
  "$KC" update clients/"$CID" -r $REALM -s "secret=$SECRET" \
    -s "redirectUris=[\"$REDIRECT\"]"
  echo "    client updated"
fi

echo "==> demo user portal-dev"
"$KC" create users -r $REALM \
  -s username=portal-dev \
  -s enabled=true \
  -s firstName=Portal -s lastName=Developer \
  -s email=portal-dev@portal.internal \
  -s emailVerified=true 2>/dev/null \
  || echo "    user already exists"
"$KC" set-password -r $REALM --username portal-dev --new-password "$PORTAL_DEV_PASSWORD"

echo "keycloak-setup: DONE"
