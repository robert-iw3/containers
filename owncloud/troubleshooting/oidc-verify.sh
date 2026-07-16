#!/bin/bash
# Verify the Authelia OIDC + forward-auth chain end to end, without a browser.
# Reads AUTHELIA_URL / OIDC client / redirect URI / TRAEFIK_HOSTNAME from .env.
#
# For local self-signed testing, export CURL_INSECURE=1 (or CACERT=...) and,
# if the hostnames don't resolve, RESOLVE="host:port:127.0.0.1 ...".
# Optional live login test: export AUTH_TEST_USER and AUTH_TEST_PASS.
source "$(dirname "$0")/_common.sh"

AUTH_URL="$(env_get AUTHELIA_URL)"
CID="$(env_get OIDC_OWNCLOUD_CLIENT_ID)"; CID="${CID:-owncloud}"
CSECRET="$(env_get OIDC_OWNCLOUD_CLIENT_SECRET)"
REDIR="$(env_get OWNCLOUD_OIDC_REDIRECT_URI)"
TRAEFIK_HOST="$(env_get TRAEFIK_HOSTNAME)"
[ -n "$AUTH_URL" ] || { bad "AUTHELIA_URL not set in $ENV_FILE"; exit 1; }

SCHEME="$(sed -nE 's#(https?)://.*#\1#p' <<<"$AUTH_URL")"
PORT="$(sed -nE 's#https?://[^:/]+:([0-9]+).*#\1#p' <<<"$AUTH_URL")"
DASH_URL="$SCHEME://$TRAEFIK_HOST${PORT:+:$PORT}"

code() { tcurl -o /dev/null -w '%{http_code}' "$@"; }
redir() { tcurl -o /dev/null -w '%{redirect_url}' "$@"; }

hdr "Authelia portal"
[ "$(code "$AUTH_URL/api/health")" = "200" ] && ok "portal /api/health 200" || bad "portal health"

hdr "OIDC discovery"
disco="$(tcurl "$AUTH_URL/.well-known/openid-configuration")"
iss="$(sed -nE 's/.*"issuer":"([^"]+)".*/\1/p' <<<"$disco")"
if [ "$iss" = "$AUTH_URL" ]; then ok "issuer matches AUTHELIA_URL ($iss)"
else bad "issuer '$iss' != AUTHELIA_URL '$AUTH_URL' (breaks token validation)"; fi
for ep in authorization_endpoint token_endpoint jwks_uri userinfo_endpoint; do
  grep -q "\"$ep\":" <<<"$disco" && ok "$ep present" || bad "$ep missing"
done

hdr "JWKS"
jwks="$(tcurl "$(sed -nE 's/.*"jwks_uri":"([^"]+)".*/\1/p' <<<"$disco")")"
grep -q '"kty":"RSA"' <<<"$jwks" && ok "RSA signing key published" || bad "no signing key"

hdr "authorize endpoint (client '$CID')"
AZ="$AUTH_URL/api/oidc/authorization"
c="$(code -G "$AZ" --data-urlencode "client_id=$CID" --data-urlencode "response_type=code" \
      --data-urlencode "scope=openid profile email" --data-urlencode "redirect_uri=$REDIR" \
      --data-urlencode "state=probe12345")"
loc="$(redir -G "$AZ" --data-urlencode "client_id=$CID" --data-urlencode "response_type=code" \
      --data-urlencode "scope=openid profile email" --data-urlencode "redirect_uri=$REDIR" \
      --data-urlencode "state=probe12345")"
if [ "$c" = "302" ] && grep -q "$AUTH_URL" <<<"$loc"; then ok "valid request -> 302 to portal login"
else bad "valid authorize returned $c (loc: ${loc:-none})"; fi
cbad="$(code -G "$AZ" --data-urlencode "client_id=$CID" --data-urlencode "response_type=code" \
      --data-urlencode "scope=openid" --data-urlencode "redirect_uri=https://evil.example/x" --data-urlencode "state=probe12345")"
[ "$cbad" = "400" ] && ok "bad redirect_uri rejected (400)" || bad "bad redirect_uri returned $cbad (expected 400)"

if [ -n "$CSECRET" ]; then
  hdr "token endpoint client auth"
  # Client-auth method differs by RP (Nextcloud user_oidc: post; ownCloud
  # openidconnect: basic). Try each (override with OIDC_TOKEN_AUTH="post basic").
  tok() { # $1=method  $2=secret  -> prints http code (400=grant bad/auth OK, 401=auth failed)
    if [ "$1" = basic ]; then
      tcurl -o /dev/null -w '%{http_code}' -u "$CID:$2" -X POST "$AUTH_URL/api/oidc/token" \
        -d grant_type=authorization_code -d code=bogus -d "redirect_uri=$REDIR"
    else
      tcurl -o /dev/null -w '%{http_code}' -X POST "$AUTH_URL/api/oidc/token" \
        -d grant_type=authorization_code -d "client_id=$CID" -d "client_secret=$2" \
        -d code=bogus -d "redirect_uri=$REDIR"
    fi
  }
  method=""
  for m in ${OIDC_TOKEN_AUTH:-post basic}; do
    [ "$(tok "$m" "$CSECRET")" = "400" ] && { method="$m"; break; }
  done
  if [ -n "$method" ]; then
    ok "correct secret -> 400 invalid_grant via client_secret_$method (client auth OK)"
    [ "$(tok "$method" WRONG)" = "401" ] && ok "wrong secret -> 401 invalid_client (negative control)" \
                                         || warn "wrong secret did not return 401"
  else
    bad "correct secret rejected by both post and basic (secret/hash mismatch, or method disabled on the client)"
  fi
else
  warn "OIDC_OWNCLOUD_CLIENT_SECRET not in .env — skipping token-endpoint check"
fi

if [ -n "$TRAEFIK_HOST" ]; then
  hdr "dashboard forward-auth"
  c="$(code "$DASH_URL/dashboard/")"; loc="$(redir "$DASH_URL/dashboard/")"
  if [ "$c" = "302" ] && grep -q "$AUTH_URL" <<<"$loc"; then ok "unauthenticated -> 302 to Authelia"
  elif [ "$c" = "401" ]; then warn "401 — dashboard on basic-auth, not forward-auth (TRAEFIK_DASHBOARD_MIDDLEWARE unset)"
  else warn "dashboard returned $c (loc: ${loc:-none})"; fi
fi

if [ -n "${AUTH_TEST_USER:-}" ] && [ -n "${AUTH_TEST_PASS:-}" ]; then
  hdr "first-factor login ($AUTH_TEST_USER)"
  r="$(tcurl -X POST "$AUTH_URL/api/firstfactor" -H 'Content-Type: application/json' \
       -d "{\"username\":\"$AUTH_TEST_USER\",\"password\":\"$AUTH_TEST_PASS\",\"keepMeLoggedIn\":false}")"
  grep -q '"status":"OK"' <<<"$r" && ok "login succeeded (user DB + hashing + Redis session)" \
                                  || bad "login failed: $r"
fi
