#!/bin/bash
# Shared helpers for the api-firewall troubleshooting scripts. Sourced, not run.
#
# Config comes from ../.env (read, never shell-sourced). Knobs:
#   FIREWALL_CONTAINER=api-firewall   target container (apifw-uat-firewall, ...)
#   EDGE_URL=http://127.0.0.1:8080    published firewall address
#   CONTAINER_ENGINE=podman           force an engine (default: docker, else podman)
#   ENV_FILE=/path/to/.env            use a different env file
#   CURL_INSECURE=1                   skip TLS verification (curl -k)
#   CACERT=/path/to/ca.crt            trust a private CA (e.g. ../certs/ca.crt.pem)

set -uo pipefail

TS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$TS_DIR")"
ENV_FILE="${ENV_FILE:-$STACK_DIR/.env}"
FW="${FIREWALL_CONTAINER:-api-firewall}"
EDGE_URL="${EDGE_URL:-http://127.0.0.1:8080}"

CE="${CONTAINER_ENGINE:-}"
if [ -z "$CE" ]; then
  if command -v docker >/dev/null 2>&1; then CE=docker
  elif command -v podman >/dev/null 2>&1; then CE=podman
  else echo "no docker/podman on PATH" >&2; exit 1; fi
fi

# Read one key from .env without sourcing the file.
env_get() {
  [ -f "$ENV_FILE" ] || return 0
  grep -m1 -E "^$1=" "$ENV_FILE" | cut -d= -f2-
}

# Read one env var from the firewall container (empty if unset/not running).
fw_env() {
  $CE inspect "$FW" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
    | grep -m1 -E "^$1=" | cut -d= -f2-
}

# curl with the optional insecure / cacert knobs applied.
tcurl() {
  local args=()
  [ "${CURL_INSECURE:-0}" = "1" ] && args+=(-k)
  [ -n "${CACERT:-}" ] && args+=(--cacert "$CACERT")
  curl -sS --max-time 10 "${args[@]}" "$@"
}

fw_running() {
  [ "$($CE inspect "$FW" --format '{{.State.Running}}' 2>/dev/null)" = "true" ]
}

if [ -t 1 ]; then G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'
else G=; R=; Y=; B=; N=; fi
ok()   { printf "  ${G}PASS${N} %s\n" "$*"; }
bad()  { printf "  ${R}FAIL${N} %s\n" "$*"; }
warn() { printf "  ${Y}WARN${N} %s\n" "$*"; }
info() { printf "  %s\n" "$*"; }
hdr()  { printf "\n${B}== %s ==${N}\n" "$*"; }
