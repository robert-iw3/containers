#!/bin/sh
set -e

# Validate arguments
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    set -- api-firewall "$@"
fi

if [ "$1" = 'api-firewall' ]; then
    shift
    set -- api-firewall "$@"
fi

# Execute with restricted permissions
exec "$@"