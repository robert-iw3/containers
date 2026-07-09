#!/bin/sh
set -e

BASE_COMMAND=cribl

if [ -z "$BASE_COMMAND" ]; then
    echo "WARNING: Entryscript in use but \$BASE_COMMAND not configured"
elif [ "${1#-}" != "${1}" ] || [ -z "$(command -v "${1}")" ] || { [ -f "${1}" ] && ! [ -x "${1}" ]; }; then
    set -- $BASE_COMMAND "$@"
fi

exec "$@"