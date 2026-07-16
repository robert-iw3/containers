#!/bin/bash
# Shared helpers for the troubleshooting scripts. Sourced, not run directly.
#
# Config comes from ../.env (read, never shell-sourced — values may contain '$'
# from bcrypt/apr1 hashes, which must not be expanded).
#
# Knobs for local / self-signed testing (unset in production):
#   CURL_INSECURE=1              skip TLS verification (curl -k)
#   CACERT=/path/to/ca.crt       trust a private CA
#   RESOLVE="host:port:ip ..."   pin DNS with curl --resolve (space-separated)
#   CONTAINER_ENGINE=podman      force an engine (default: docker, else podman)
#   ENV_FILE=/path/to/.env       use a different env file

set -uo pipefail

TS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$TS_DIR")"
STACK_NAME="$(basename "$STACK_DIR")"          # e.g. "nextcloud" -> network prefix
ENV_FILE="${ENV_FILE:-$STACK_DIR/.env}"

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

# curl with the optional insecure / cacert / resolve knobs applied.
tcurl() {
  local args=() r
  [ "${CURL_INSECURE:-0}" = "1" ] && args+=(-k)
  [ -n "${CACERT:-}" ] && args+=(--cacert "$CACERT")
  for r in ${RESOLVE:-}; do args+=(--resolve "$r"); done
  curl -sS "${args[@]}" "$@"
}

if [ -t 1 ]; then G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'
else G=; R=; Y=; B=; N=; fi
ok()   { printf "  ${G}PASS${N} %s\n" "$*"; }
bad()  { printf "  ${R}FAIL${N} %s\n" "$*"; }
warn() { printf "  ${Y}WARN${N} %s\n" "$*"; }
hdr() { printf "\n${B}== %s ==${N}\n" "$*"; }
