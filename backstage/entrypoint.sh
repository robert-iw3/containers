#!/bin/bash
# Pull the portal's runtime secrets from Vault, then exec the Backstage
# backend. When VAULT_TOKEN_FILE is unset the container expects POSTGRES_* /
# GITEA_* to be provided by the platform (e.g. k8s with an external secret
# store) and starts directly.
set -euo pipefail

APP_CONFIG=${APP_CONFIG:-app-config.yaml}

vault_get() { # vault_get <api-path> -> response json on stdout
    curl -sf --cacert "$VAULT_CACERT" \
        -H "X-Vault-Token: $(cat "$VAULT_TOKEN_FILE")" \
        "$VAULT_ADDR/v1/$1"
}

json_get() { # json_get <json> <dot.path>
    node -e '
        const v = process.argv[2].split(".").reduce((o, k) => o && o[k], JSON.parse(process.argv[1]));
        if (v == null) process.exit(1);
        console.log(v);
    ' "$1" "$2"
}

if [ -n "${VAULT_TOKEN_FILE:-}" ]; then
    echo "entrypoint: waiting for Vault token at $VAULT_TOKEN_FILE"
    for _ in $(seq 1 150); do
        [ -s "$VAULT_TOKEN_FILE" ] && break
        sleep 2
    done
    [ -s "$VAULT_TOKEN_FILE" ] || { echo "entrypoint: FAIL no Vault token appeared"; exit 1; }

    echo "entrypoint: fetching rotated database credentials"
    CREDS=""
    for _ in $(seq 1 60); do
        CREDS=$(vault_get "database/static-creds/backstage-portal") && break
        CREDS=""
        sleep 2
    done
    [ -n "$CREDS" ] || { echo "entrypoint: FAIL could not read database/static-creds/backstage-portal"; exit 1; }
    POSTGRES_USER=$(json_get "$CREDS" data.username)
    POSTGRES_PASSWORD=$(json_get "$CREDS" data.password)
    export POSTGRES_USER POSTGRES_PASSWORD

    echo "entrypoint: fetching Gitea credentials from kv"
    GITEA_SECRET=""
    for _ in $(seq 1 150); do
        GITEA_SECRET=$(vault_get "secret/data/gitea/portal") && break
        GITEA_SECRET=""
        sleep 2
    done
    [ -n "$GITEA_SECRET" ] || { echo "entrypoint: FAIL could not read secret/data/gitea/portal"; exit 1; }
    GITEA_USERNAME=$(json_get "$GITEA_SECRET" data.data.username)
    GITEA_PASSWORD=$(json_get "$GITEA_SECRET" data.data.password)
    export GITEA_USERNAME GITEA_PASSWORD

    echo "entrypoint: fetching OIDC client secret from kv"
    OIDC_SECRET_JSON=""
    for _ in $(seq 1 150); do
        OIDC_SECRET_JSON=$(vault_get "secret/data/oidc/portal") && break
        OIDC_SECRET_JSON=""
        sleep 2
    done
    [ -n "$OIDC_SECRET_JSON" ] || { echo "entrypoint: FAIL could not read secret/data/oidc/portal"; exit 1; }
    OIDC_CLIENT_SECRET=$(json_get "$OIDC_SECRET_JSON" data.data.client_secret)
    export OIDC_CLIENT_SECRET

    echo "entrypoint: secrets loaded (db user: $POSTGRES_USER)"
fi

exec node packages/backend --config "$APP_CONFIG"
