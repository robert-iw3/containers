#!/usr/bin/dumb-init /bin/sh
set -e

ulimit -c 0

if [ "${1:0:1}" = '-' ]; then
    set -- boundary "$@"
fi

if [ "$1" = 'server' ]; then
    shift
    set -- boundary server "$@"
elif boundary --help "$1" 2>&1 | grep -q "boundary $1"; then
    set -- boundary "$@"
fi

if [ "$1" = 'boundary' ]; then
    if [ -z "$SKIP_CHOWN" ]; then
        if [ "$(stat -c %u /boundary)" != "$(id -u boundary)" ]; then
            chown -R boundary:boundary /boundary || echo "Could not chown /boundary (may not have appropriate permissions)"
        fi
    fi

    if [ -z "$SKIP_SETCAP" ]; then
        setcap cap_ipc_lock=+ep $(readlink -f $(which boundary)) || {
            echo "Couldn't set IPC_LOCK. Disabling IPC_LOCK."
            setcap cap_ipc_lock=-ep $(readlink -f $(which boundary))
        }
    fi

    if [ "$(id -u)" = '0' ]; then
        set -- su-exec boundary "$@"
    fi
fi

exec "$@"