#!/usr/bin/dumb-init /bin/sh
set -e

# Prevent core dumps
ulimit -c 0

# Allow setting VAULT_REDIRECT_ADDR and VAULT_CLUSTER_ADDR using an interface
get_addr () {
    local if_name=$1
    local uri_template=$2
    ip addr show dev $if_name | awk -v uri=$uri_template '/\s*inet\s/ { \
      ip=gensub(/(.+)\/.+/, "\\1", "g", $2); \
      print gensub(/^(.+:\/\/).+(:.+)$/, "\\1" ip "\\2", "g", uri); \
      exit}'
}

if [ -n "$VAULT_REDIRECT_INTERFACE" ]; then
    export VAULT_REDIRECT_ADDR=$(get_addr $VAULT_REDIRECT_INTERFACE ${VAULT_REDIRECT_ADDR:-"https://0.0.0.0:8200"})
    echo "Using $VAULT_REDIRECT_INTERFACE for VAULT_REDIRECT_ADDR: $VAULT_REDIRECT_ADDR"
fi
if [ -n "$VAULT_CLUSTER_INTERFACE" ]; then
    export VAULT_CLUSTER_ADDR=$(get_addr $VAULT_CLUSTER_INTERFACE ${VAULT_CLUSTER_ADDR:-"https://0.0.0.0:8201"})
    echo "Using $VAULT_CLUSTER_INTERFACE for VAULT_CLUSTER_ADDR: $VAULT_CLUSTER_ADDR"
fi

VAULT_CONFIG_DIR=/vault/config

if [ -n "$VAULT_LOCAL_CONFIG" ]; then
    echo "$VAULT_LOCAL_CONFIG" > "$VAULT_CONFIG_DIR/local.json"
fi

if [ "${1:0:1}" = '-' ]; then
    set -- vault "$@"
fi

if [ "$1" = 'server' ]; then
    shift
    set -- vault server \
        -config="$VAULT_CONFIG_DIR" \
        -dev-root-token-id="$VAULT_DEV_ROOT_TOKEN_ID" \
        -dev-listen-address="${VAULT_DEV_LISTEN_ADDRESS:-"0.0.0.0:8200"}" \
        "$@"
elif [ "$1" = 'version' ]; then
    set -- vault "$@"
elif vault --help "$1" 2>&1 | grep -q "vault $1"; then
    set -- vault "$@"
fi

if [ "$1" = 'vault' ]; then
    if [ -z "$SKIP_CHOWN" ]; then
        if [ "$(stat -c %u /vault/config)" != "$(id -u vault)" ]; then
            chown -R vault:vault /vault/config || echo "Could not chown /vault/config"
        fi
        if [ "$(stat -c %u /vault/logs)" != "$(id -u vault)" ]; then
            chown -R vault:vault /vault/logs
        fi
        if [ "$(stat -c %u /vault/data)" != "$(id -u vault)" ]; then
            chown -R vault:vault /vault/data
        fi
        if [ "$(stat -c %u /certs)" != "$(id -u vault)" ]; then
            chown -R vault:vault /certs
        fi
    fi

    if [ -z "$SKIP_SETCAP" ]; then
        setcap cap_ipc_lock=+ep $(readlink -f $(which vault))
        if ! vault -version 1>/dev/null 2>/dev/null; then
            >&2 echo "Couldn't start vault with IPC_LOCK. Disabling IPC_LOCK"
            setcap cap_ipc_lock=-ep $(readlink -f $(which vault))
        fi
    fi

    if [ "$(id -u)" = '0' ]; then
        set -- su-exec vault "$@"
    fi
fi

exec "$@"