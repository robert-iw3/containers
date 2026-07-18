#!/bin/sh
set -e

# Run api-firewall by default; allow `docker run ... <flags>` shorthand and
# arbitrary commands (e.g. `docker run ... sh`) to pass through.
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    set -- api-firewall "$@"
fi

# api-firewall resolves the backend host once at startup and exits if the
# lookup fails, which loses the race against a backend container whose DNS
# record is still propagating. Wait (bounded) for the name to appear; on
# timeout, start anyway and let the restart policy take over.
if [ "$1" = "api-firewall" ] && [ -n "${APIFW_SERVER_URL:-}" ]; then
    host="${APIFW_SERVER_URL#*://}"; host="${host%%/*}"; host="${host%%:*}"
    timeout="${APIFW_STARTUP_DNS_TIMEOUT:-30}"
    i=0
    until nslookup "$host" >/dev/null 2>&1; do
        i=$((i + 1))
        if [ "$i" -ge "$timeout" ]; then
            echo "entrypoint: '$host' still unresolved after ${timeout}s, starting anyway" >&2
            break
        fi
        [ "$i" -eq 1 ] && echo "entrypoint: waiting for '$host' to resolve..." >&2
        sleep 1
    done
fi

exec "$@"
