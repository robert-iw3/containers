#!/bin/bash
# Configure ownCloud to use Authelia as an OpenID Connect provider.
# Installs the openidconnect app and writes its config via occ, using values
# from .env. Run after the stack is up with the sso profile:
#
#   docker compose -f docker-compose.yml -f docker-compose.sso.yml \
#     --profile sso up -d
#   ./owncloud-configure-oidc.sh
#
# Sync/mobile/DAV clients keep working with app passwords; this adds SSO to the
# web login. Re-running is safe (config:system:set is idempotent).
set -euo pipefail
cd "$(dirname "$0")"

# Read keys from .env WITHOUT shell-sourcing (values may contain '$').
env_get() { grep -m1 -E "^$1=" .env | cut -d= -f2-; }

AUTHELIA_URL="$(env_get AUTHELIA_URL)"
CLIENT_ID="$(env_get OIDC_OWNCLOUD_CLIENT_ID)"; CLIENT_ID="${CLIENT_ID:-owncloud}"
CLIENT_SECRET="$(env_get OIDC_OWNCLOUD_CLIENT_SECRET)"
PROVIDER_NAME="$(env_get OIDC_PROVIDER_NAME)"; PROVIDER_NAME="${PROVIDER_NAME:-Authelia}"

APP=owncloud-app
occ() { docker exec "$APP" occ "$@"; }

echo "--> Ensuring openidconnect app is installed..."
if ! occ app:list | grep -q openidconnect; then
  # The sso overlay puts the app container on the frontend network so the
  # marketplace (and later the OIDC issuer) are reachable.
  occ market:install openidconnect
fi
occ app:enable openidconnect

echo "--> Writing openid-connect config..."
occ config:system:set openid-connect provider-url     --value="$AUTHELIA_URL"
occ config:system:set openid-connect client-id        --value="$CLIENT_ID"
occ config:system:set openid-connect client-secret    --value="$CLIENT_SECRET"
occ config:system:set openid-connect loginButtonName  --value="$PROVIDER_NAME"
# Match the OIDC identity to an ownCloud account by its uid == preferred_username.
occ config:system:set openid-connect mode             --value=userid
occ config:system:set openid-connect search-attribute --value=preferred_username
# Autodiscovery endpoint (Authelia serves the standard well-known document).
occ config:system:set openid-connect autodiscovery-url \
  --value="$AUTHELIA_URL/.well-known/openid-configuration"

# Auto-provision accounts for SSO end users (who are not host admins and have no
# pre-existing local account). Local admins keep logging in with the username/
# password form on /login; this only governs the Authelia path.
occ config:system:set openid-connect auto-provision enabled           --value=true --type=boolean
occ config:system:set openid-connect auto-provision email-claim       --value=email
occ config:system:set openid-connect auto-provision display-name-claim --value=name
# Keep display-name/email in sync on subsequent logins.
occ config:system:set openid-connect auto-update enabled --value=true --type=boolean

echo "--> Done."
echo "    * Admins log in with the local username/password form on /login."
echo "    * End users click \"Log in with $PROVIDER_NAME\"; new users are auto-provisioned."
echo "    NOTE: with mode=userid the OIDC 'preferred_username' maps to the ownCloud"
echo "    uid — keep your IdP usernames distinct from privileged local accounts."
echo "    Verify discovery is reachable from the app container:"
echo "    docker exec $APP curl -sS $AUTHELIA_URL/.well-known/openid-configuration | head -c 200"
