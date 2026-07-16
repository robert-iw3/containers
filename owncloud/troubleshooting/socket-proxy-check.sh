#!/bin/bash
# Verify the container-engine socket proxy: it must be healthy, ALLOW the
# read-only discovery endpoints Traefik needs, and DENY everything else. Also
# surfaces Traefik provider-connection errors (dead socket / unreachable proxy).
#
# Runs the allow/deny probes from an ephemeral curl container on the isolated
# socket network (the proxy is not published to the host).
source "$(dirname "$0")/_common.sh"
PROXY="${STACK_NAME}-socket-proxy"
TRAEFIK="${STACK_NAME}-traefik"
NET="${STACK_NAME}_socket"

hdr "socket proxy container"
status="$($CE inspect -f '{{.State.Status}}/{{.State.Health.Status}}' "$PROXY" 2>/dev/null)" || { bad "$PROXY not found"; exit 1; }
case "$status" in */healthy) ok "$PROXY: $status" ;; *) bad "$PROXY: $status"; $CE logs --tail 5 "$PROXY" 2>&1 ;; esac

probe() { # method path expected  label
  local code
  code="$($CE run --rm --network "$NET" docker.io/curlimages/curl:latest \
          -s -o /dev/null -w '%{http_code}' -X "$1" "http://socket-proxy:2375$2" 2>/dev/null)"
  if [ "$code" = "$3" ]; then ok "$4 ($1 $2 -> $code)"; else bad "$4 ($1 $2 -> $code, expected $3)"; fi
}

hdr "API filter (allow discovery, deny the rest)"
probe GET  /version                 200 "version allowed"
probe GET  /v1.40/containers/json   200 "container discovery allowed"
probe GET  /v1.40/networks          200 "network discovery allowed"
probe POST /v1.40/containers/create 403 "container create DENIED"
probe GET  /v1.40/images/json       403 "image listing DENIED"
probe GET  /v1.40/info              403 "host info DENIED"
probe GET  /v1.40/exec/x/json       403 "exec DENIED"

hdr "Traefik provider connectivity ($TRAEFIK, last 2m)"
if $CE logs --since 2m "$TRAEFIK" 2>&1 | grep -iqE 'cannot connect to the docker daemon|provider error'; then
  bad "Traefik cannot reach the socket proxy / engine endpoint"
  echo "     -> check the proxy above; if the host socket is down run ./podman-socket.sh --repair"
else
  ok "no provider connection errors"
fi
