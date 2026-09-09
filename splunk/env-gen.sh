#!/usr/bin/env bash
# Generate the Authentik secrets in authentik-compose.yml's .env.
#
#   ./env-gen.sh              write .env, refusing to clobber an existing one
#   ./env-gen.sh --force      regenerate, invalidating existing sessions
#
# Appending is not idempotent: a second run leaves two values for every key,
# and which one wins depends on the reader. This writes the file whole.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${HERE}/.env"

if [[ -f "$ENV_FILE" && "${1:-}" != "--force" ]]; then
    echo "$ENV_FILE exists. Re-run with --force to regenerate."
    echo "A new AUTHENTIK_SECRET_KEY invalidates every existing session."
    exit 1
fi

# tr -d '\n' matters: a newline inside a compose value truncates it silently.
umask 077
cat > "$ENV_FILE" <<EOF
PG_USER=authentik
PG_DB=authentik
PG_PASS=$(openssl rand -base64 36 | tr -d '\n')
AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n')
AUTHENTIK_ERROR_REPORTING__ENABLED=true
EOF

echo "wrote $ENV_FILE ($(grep -c . "$ENV_FILE") settings, mode $(stat -c %a "$ENV_FILE"))"
