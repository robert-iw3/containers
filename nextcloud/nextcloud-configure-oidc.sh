#!/bin/bash
# Configure Nextcloud to use Authelia as an OpenID Connect provider.
# Installs the user_oidc app and registers the "Authelia" provider using values
# from .env. Run after the stack is up with the sso profile:
#
#   docker compose -f docker-compose.yml -f docker-compose.sso.yml \
#     --profile sso up -d
#   ./nextcloud-configure-oidc.sh
#
# Desktop/mobile/DAV clients keep working with app passwords; this only adds an
# SSO button to the web login. Re-running is safe (upsert semantics).
set -euo pipefail

cd "$(dirname "$0")"

# Read a key from .env WITHOUT shell-sourcing it: values may contain '$'
# (e.g. bcrypt/apr1 hashes) that must never be expanded.
env_get() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }

AUTHELIA_URL="$(env_get AUTHELIA_URL)"
OIDC_NEXTCLOUD_CLIENT_ID="$(env_get OIDC_NEXTCLOUD_CLIENT_ID)"
OIDC_NEXTCLOUD_CLIENT_SECRET="$(env_get OIDC_NEXTCLOUD_CLIENT_SECRET)"
OIDC_PROVIDER_NAME="$(env_get OIDC_PROVIDER_NAME)"

APP=nextcloud-app
PROVIDER_NAME="${OIDC_PROVIDER_NAME:-Authelia}"
DISCOVERY="${AUTHELIA_URL}/.well-known/openid-configuration"

occ() { docker exec -u www-data "$APP" php occ "$@"; }

echo "--> Ensuring user_oidc is installed..."
if ! occ app:list | grep -q user_oidc; then
  # The app container has no egress by default; the sso overlay puts it on the
  # frontend network. If install still fails, fetch on a host with egress.
  occ app:install user_oidc
fi
occ app:enable user_oidc

echo "--> Allowing OIDC to coexist with local accounts (clients use app passwords)..."
occ config:app:set user_oidc allow_multiple_user_backends --value=1

echo "--> Registering provider \"$PROVIDER_NAME\" (discovery: $DISCOVERY)..."
# upsert: user_oidc:provider updates the provider if the name already exists.
occ user_oidc:provider "$PROVIDER_NAME" \
  --clientid="${OIDC_NEXTCLOUD_CLIENT_ID:-nextcloud}" \
  --clientsecret="${OIDC_NEXTCLOUD_CLIENT_SECRET}" \
  --discoveryuri="$DISCOVERY" \
  --scope="openid email profile groups" \
  --mapping-uid=preferred_username \
  --mapping-email=email \
  --mapping-display-name=name \
  --unique-uid=0 \
  --check-bearer=0 \
  --send-id-token-hint=1

echo "--> Done. The Nextcloud login page now shows a \"Log in with $PROVIDER_NAME\" button."
echo "    Verify discovery is reachable from the app container:"
echo "    docker exec -u www-data $APP curl -sS $DISCOVERY | head -c 200"
