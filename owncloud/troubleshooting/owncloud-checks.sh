#!/bin/bash
# Common ownCloud (occ) health checks for the classic 10.x stack — the
# equivalent of nextcloud-checks.sh. The classic stack has no OIDC/Authelia, so
# there is no back-channel/OIDC section here.
#
# NOTE: targets ownCloud 10 `occ`; not yet exercised against a live instance
# (the ownCloud stack has only had static validation). Every occ call tolerates
# failure so a version mismatch degrades gracefully rather than aborting.
source "$(dirname "$0")/_common.sh"
APP="${STACK_NAME}-app"
# The owncloud/server image ships an `occ` wrapper that runs as the web user.
occ() { $CE exec "$APP" occ "$@" 2>/dev/null; }

$CE inspect "$APP" >/dev/null 2>&1 || { bad "$APP not found (is the stack running?)"; exit 1; }

hdr "install / maintenance / version"
if occ status | sed 's/^/  /'; then :; else bad "occ status failed (DB down, or occ path differs on this version)"; fi

hdr "background jobs (should be 'cron' in production, not ajax)"
occ config:app:get core backgroundjobs_mode | sed 's/^/  /' || warn "could not read backgroundjobs_mode"

hdr "redis / cache wiring"
for k in memcache.local memcache.locking; do
  printf "  %-22s %s\n" "$k" "$(occ config:system:get "$k" 2>/dev/null || echo '(unset)')"
done
# redis config is a multi-line array containing the password — redact + collapse.
redis_cfg="$(occ config:system:get redis 2>/dev/null | sed -E 's/(password:).*/\1 ***set***/' | tr '\n' ' ')"
printf "  %-22s %s\n" "redis" "${redis_cfg:-(unset)}"

hdr "trusted domains / overwrite settings"
for k in trusted_domains overwrite.cli.url overwritehost overwriteprotocol; do
  printf "  %-22s %s\n" "$k" "$(occ config:system:get "$k" 2>/dev/null | tr '\n' ' ' || echo '(unset)')"
done

hdr "app healthcheck (also proves DB reachability)"
if $CE exec "$APP" /usr/bin/healthcheck >/dev/null 2>&1; then
  ok "image healthcheck passed"
else
  bad "image healthcheck failed — check ./stack-health.sh owncloud and DB/Redis"
fi
