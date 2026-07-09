#!/bin/bash

# Exit on error
set -e

# Log function for persistent logging
log() {
    echo "$(date -u) - $1" | tee -a /usr/local/zeek/logs/zeek_entrypoint.log
}

# Validate network interface
if [ ! -z "$ZEEK_INTERFACE" ]; then
    ip link show "$ZEEK_INTERFACE" >/dev/null 2>&1 || {
        log "ERROR: Interface $ZEEK_INTERFACE not found"
        exit 1
    }
fi

# Generate node.cfg if not present
if [ ! -f /usr/local/zeek/etc/node.cfg ] || [ ! -s /usr/local/zeek/etc/node.cfg ]; then
    log "Generating node.cfg with interface ${ZEEK_INTERFACE:-eth0}"
    zeekcfg -o /usr/local/zeek/etc/node.cfg --type afpacket --interface "${ZEEK_INTERFACE:-eth0}" --processes "${ZEEK_WORKER_PROCESSES:-4}" --no-pin
fi

# Final log rotation and cleanup
stop() {
    log "Stopping Zeek..."
    zeekctl stop
    trap - SIGINT SIGTERM
    exit 0
}

# Run diagnostics on error
diag() {
    log "Running zeekctl diag for debugging"
    zeekctl diag >> /usr/local/zeek/logs/zeek_diag.log 2>&1
    trap - ERR
}
trap 'diag' ERR
trap 'stop' SIGINT SIGTERM

# Ensure Zeek configuration
log "Checking Zeek configuration..."
cat /usr/local/zeek/share/zeek/site/autoload/* | grep -v '^#' | grep -v 'misc/scan' > /usr/local/zeek/share/zeek/site/local.zeek
zeekctl check >/dev/null
zeekctl install
zeekctl start

# Enable cron for Zeek maintenance
log "Enabling Zeek cron..."
zeekctl cron enable

# Start cron in foreground with logging
log "Starting cron daemon..."
crond -f -L /usr/local/zeek/logs/cron.log &

# Keep container running
wait