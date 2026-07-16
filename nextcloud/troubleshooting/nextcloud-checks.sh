#!/bin/bash
# Common Nextcloud (occ) health checks plus the OIDC back-channel reachability
# test — i.e. can the app container actually reach the OIDC issuer server-side.
# The back-channel is the #1 non-obvious OIDC failure (SSRF guard on local
# hostnames, unresolvable issuer, or an untrusted cert).
source "$(dirname "$0")/_common.sh"
APP="${STACK_NAME}-app"
occ() { $CE exec -u www-data "$APP" php occ "$@" 2>/dev/null; }

$CE inspect "$APP" >/dev/null 2>&1 || { bad "$APP not found"; exit 1; }

hdr "install / maintenance"
occ status | grep -E 'installed|versionstring|maintenance|needsDbUpgrade' | sed 's/^/  /'

hdr "background jobs (must be 'cron' in production, not ajax)"
occ background:job:mode 2>/dev/null | sed 's/^/  /' || occ config:app:get core backgroundjobs_mode 2>/dev/null | sed 's/^/  /'

hdr "setup warnings (db indices / missing columns)"
mi="$(occ db:add-missing-indices --dry-run 2>/dev/null | grep -i 'add' | head)"
[ -z "$mi" ] && ok "no missing indices" || { warn "missing indices:"; echo "$mi" | sed 's/^/    /'; }

hdr "OIDC providers (user_oidc)"
if occ app:list | grep -q user_oidc; then
  occ user_oidc:provider 2>/dev/null | grep -E '^\|' | sed 's/^/  /'
  DISCO="$(occ config:system:get user_oidc 2>/dev/null)"
  ISSUER="$(env_get AUTHELIA_URL)"
  if [ -n "$ISSUER" ]; then
    hdr "OIDC back-channel: $APP -> $ISSUER"
    # app container uses Nextcloud's HTTP client; here we test raw reachability +
    # TLS trust with the system bundle (a 200 or a TLS complaint both prove the
    # name resolves and routes; connection-refused means DNS/routing is broken).
    out="$($CE exec "$APP" sh -c "curl -sS -o /dev/null -w '%{http_code}' --max-time 8 '$ISSUER/.well-known/openid-configuration' 2>&1")"
    case "$out" in
      200) ok "discovery reachable and TLS-trusted (200)" ;;
      000*|*"Could not resolve"*|*"Failed to connect"*|*refused*)
        bad "cannot reach issuer: $out"
        echo "     -> DNS/routing: is the app on a network that reaches the issuer host?"
        echo "        (libcurl shortcuts *.localhost to loopback — don't use .localhost issuers)" ;;
      *"certificate"*|*"SSL"*)
        warn "reachable but system curl distrusts the cert: $out"
        echo "     Nextcloud's own client uses its bundle; import your CA with:"
        echo "       $CE exec -u www-data $APP php occ security:certificates:import /path/ca.crt" ;;
      *) warn "unexpected: $out" ;;
    esac
  fi
else
  warn "user_oidc not installed (run ../nextcloud-configure-oidc.sh)"
fi

hdr "trusted proxies / overwrite settings"
for k in trusted_proxies overwriteprotocol overwrite.cli.url; do
  printf "  %-22s %s\n" "$k" "$(occ config:system:get "$k" 2>/dev/null || echo '(unset)')"
done
