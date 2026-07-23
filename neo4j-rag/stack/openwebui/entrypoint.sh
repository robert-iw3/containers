#!/usr/bin/env bash
# OpenWebUI launch shim: trust the stack CA for the server-side OIDC token
# exchange (OpenWebUI's HTTP client uses certifi's bundle), then start normally.
# Harmless when no custom CA is mounted (real/public certs in production).
set -e

PY="$(command -v python3 || command -v python || true)"
if [ -f /certs/ca.crt ] && [ -n "$PY" ]; then
    BUNDLE="$("$PY" -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
    if [ -n "$BUNDLE" ] && ! grep -qFf /certs/ca.crt "$BUNDLE" 2>/dev/null; then
        cat /certs/ca.crt >> "$BUNDLE" || true
    fi
fi

exec bash start.sh
