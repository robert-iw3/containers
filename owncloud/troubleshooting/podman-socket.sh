#!/bin/bash
# Diagnose (and with --repair, fix) the rootless podman API socket Traefik uses
# for service discovery via the socket proxy. Covers the two failure modes hit
# in practice:
#   1. socket unit inactive  -> Traefik/proxy log "Cannot connect to Docker daemon"
#   2. socket PATH is a directory -> a bind-mount of a then-missing socket auto-
#      created a dir, and the systemd unit now fails to listen on it.
#
#   ./podman-socket.sh            # diagnose only
#   ./podman-socket.sh --repair   # remove stale dir, (re)start podman.socket
source "$(dirname "$0")/_common.sh"

SOCK="$(env_get DOCKER_SOCKET)"
SOCK="${SOCK:-/run/user/$(id -u)/podman/podman.sock}"
REPAIR=0; [ "${1:-}" = "--repair" ] && REPAIR=1

ping_ok() { curl -s --max-time 3 --unix-socket "$SOCK" http://d/v1.40/_ping >/dev/null 2>&1; }

hdr "podman API socket: $SOCK"
if [ -S "$SOCK" ] && ping_ok; then
  ok "live socket, answers _ping"; exit 0
fi
if [ -d "$SOCK" ]; then bad "path is a DIRECTORY (bind-mount footgun) — unusable"
elif [ -S "$SOCK" ]; then bad "socket exists but does not answer (unit stopped?)"
else bad "socket missing"; fi
systemctl --user status podman.socket --no-pager 2>&1 | grep -E 'Active:|Listen:' | sed 's/^/  /'

if [ "$REPAIR" != "1" ]; then
  printf "\nRe-run with ${B}--repair${N} to fix.\n"; exit 1
fi

hdr "repairing"
if [ -d "$SOCK" ]; then
  echo "  removing stale directory"
  rmdir "$SOCK" 2>/dev/null || rm -rf "$SOCK"
fi
systemctl --user reset-failed podman.socket 2>/dev/null || true
systemctl --user start podman.socket || { bad "start failed — journalctl --user -xe -u podman.socket"; exit 1; }
sleep 1
if ping_ok; then
  ok "socket restored"
  echo "  If Traefik/proxy were already running, restart them so they reconnect:"
  echo "    $CE restart ${STACK_NAME}-socket-proxy ${STACK_NAME}-traefik"
else
  bad "still not answering — journalctl --user -xe -u podman.socket"; exit 1
fi
