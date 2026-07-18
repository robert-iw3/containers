#!/bin/bash
# Diagnose firewall -> backend connectivity from INSIDE the firewall
# container: DNS resolution, then an HTTP fetch of the backend URL. This is
# the check to run when the firewall crash-loops with "failed to resolve
# host" or readiness fails.
#
#   ./backend-check.sh              # target = APIFW_SERVER_URL of the container
#   ./backend-check.sh http://api:8000/health
source "$(dirname "$0")/_common.sh"

TARGET="${1:-$(fw_env APIFW_SERVER_URL)}"

hdr "firewall -> backend connectivity ($FW)"
fw_running || { bad "$FW is not running — run ./firewall-probe.sh first"; exit 1; }
[ -n "$TARGET" ] || { bad "no target: APIFW_SERVER_URL unset and no argument given"; exit 1; }
info "target: $TARGET"

host="${TARGET#*://}"; host="${host%%/*}"; host="${host%%:*}"

hdr "DNS: $host"
if $CE exec "$FW" nslookup "$host" >/dev/null 2>&1; then
  addr="$($CE exec "$FW" nslookup "$host" 2>/dev/null | awk '/^Address/ {a=$2} END {print a}')"
  ok "resolves ($addr)"
else
  bad "does not resolve from inside the container"
  info "  - backend on the same network? (compose 'backend'/'uat-internal', or"
  info "    'docker network connect <net> <backend-container>')"
  info "  - service name vs container name: DNS uses the compose service name"
  exit 1
fi

hdr "HTTP fetch"
out="$($CE exec "$FW" wget -q -O /dev/null -S "$TARGET" 2>&1)"
rc=$?
out="$(printf '%s\n' "$out" | grep -v "Emulate Docker CLI")"
first="$(printf '%s\n' "$out" | sed -n 1p)"
if [ $rc -eq 0 ] || printf '%s' "$out" | grep -q "HTTP/"; then
  ok "backend answers: ${first:-connected}"
else
  # wget exit 8 = server issued an error response (4xx/5xx) — still reachable.
  if [ $rc -eq 8 ]; then
    ok "backend reachable (returned an HTTP error status for $TARGET — often fine for /)"
  else
    bad "no HTTP response (exit $rc) — port wrong, backend down, or TLS mismatch"
    info "  - https backend with private CA? set APIFW_SERVER_ROOT_CA"
    exit 1
  fi
fi
exit 0
