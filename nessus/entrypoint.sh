#!/bin/bash
# Activate Nessus with provided code or exit
ACTIVATION_CODE=${ACTIVATION_CODE:-}
if [ -z "$ACTIVATION_CODE" ]; then
    echo "ERROR: ACTIVATION_CODE not provided"
    exit 1
fi
/opt/nessus/sbin/nessuscli fetch --register "$ACTIVATION_CODE"
/opt/nessus/sbin/nessuscli update --all
exec /opt/nessus/sbin/nessus-service --no-root -q -D