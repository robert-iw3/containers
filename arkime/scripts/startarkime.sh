#!/bin/bash

# Exit on any error
set -e

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Wait for OpenSearch to be ready
wait_for_opensearch() {
    log "Waiting for OpenSearch to start at $OS_HOST:$OS_PORT..."
    until curl -sS "http://$OS_HOST:$OS_PORT/_cluster/health?wait_for_status=green" > /dev/null 2>&1; do
        log "OpenSearch not ready, retrying..."
        sleep 1
    done
    log "OpenSearch started"
}

# Initialize or upgrade Arkime database
initialize_arkime() {
    local initialized_file="$ARKIMEDIR/etc/.initialized"
    local config_cmd="$ARKIMEDIR/bin/Configure"
    local db_cmd="$ARKIMEDIR/db/db.pl"

    # Generate random password if not set
    export ARKIME_PASSWORD=${ARKIME_PASSWORD:-$(tr -cd '[:alnum:]' < /dev/urandom | fold -w32 | head -n1)}
    export ARKIME_LOCALELASTICSEARCH=${ARKIME_LOCALELASTICSEARCH:-no}
    export ARKIME_ELASTICSEARCH="http://$OS_HOST:$OS_PORT"
    export ARKIME_INET=${ARKIME_INET:-no}

    if [ ! -f "$initialized_file" ]; then
        log "Initializing Arkime database..."
        if [ -z "$OS_USER" ]; then
            echo -e "$ARKIME_LOCALELASTICSEARCH\n\n$ARKIME_INET" | $config_cmd
        else
            echo -e "$ARKIME_LOCALELASTICSEARCH\n$OS_USER\n$OS_PASSWORD\n$ARKIME_INET" | $config_cmd
        fi
        echo INIT | $db_cmd http://$OS_HOST:$OS_PORT init
        $ARKIMEDIR/bin/arkime_add_user.sh admin "Admin User" "$ARKIME_ADMIN_PASSWORD" --admin
        echo "$ARKIME_VERSION" > "$initialized_file"
    else
        local old_ver
        read -r old_ver < "$initialized_file"
        local newer_ver=$(echo -e "$old_ver\n$ARKIME_VERSION" | sort -rV | head -n 1)
        if [ "$old_ver" != "$newer_ver" ]; then
            log "Upgrading Arkime database..."
            echo -e "$ARKIME_LOCALELASTICSEARCH\n$ARKIME_INET" | $config_cmd
            $db_cmd http://$OS_HOST:$OS_PORT upgradenoprompt
            echo "$ARKIME_VERSION" > "$initialized_file"
        fi
    fi
}

# Configure Suricata plugin
configure_suricata() {
    if [ "$SURICATA" = "on" ]; then
        log "Configuring Suricata plugin..."
        mkdir -p /data/suricata
        chmod 757 /data/suricata
        chown -R nobody:daemon /data/suricata
        {
            echo "plugins=suricata.so"
            echo "suricataAlertFile=/data/suricata/eve.json"
        } >> "$ARKIMEDIR/etc/config.ini"
        if [ -x "/data/append_config.sh" ]; then
            bash -c "/data/append_config.sh" || log "Warning: append_config.sh failed"
        fi
    fi
}

# Configure proxy
configure_proxy() {
    if [ "$PROXY" = "on" ]; then
        log "Configuring proxy..."
        sed -i '/^\[default\]/a webBasePath=/arkime/' "$ARKIMEDIR/etc/config.ini"
    fi
}

# Configure WISE service部分

configure_wise() {
    if [ "$WISE" = "on" ]; then
        log "Configuring WISE service..."
        sed -i '/^\[default\]/a wiseHost=127.0.0.1\nwisePort=8081\nplugins=wise.so\nviewerPlugins=wise.js' "$ARKIMEDIR/etc/config.ini"
        if [ -f "$ARKIMEDIR/etc/wise.ini" ]; then
            log "Starting WISE service..."
            rm -f "$ARKIMEDIR/logs/wise*"
            pushd "$ARKIMEDIR/wiseService" > /dev/null
            $ARKIMEDIR/bin/node wiseService.js --insecure -c "$ARKIMEDIR/etc/wise.ini" >> "$ARKIMEDIR/logs/wise.log" 2>&1 &
            popd > /dev/null
        fi
    fi
}

# Start capture
start_capture() {
    if [ "$CAPTURE" = "on" ]; then
        log "Starting packet capture..."
        chmod 757 /data/pcap
        $ARKIMEDIR/bin/capture --config "$ARKIMEDIR/etc/config.ini" --host "$ARKIME_HOSTNAME" >> "$ARKIMEDIR/logs/capture.log" 2>&1 &
    fi
}

# Start viewer
start_viewer() {
    if [ "$VIEWER" = "on" ]; then
        log "Starting Arkime viewer..."
        log "Visit http://127.0.0.1:8005"
        log "  user: admin"
        log "  password: $ARKIME_ADMIN_PASSWORD"
        pushd "$ARKIMEDIR/viewer" > /dev/null
        $ARKIMEDIR/bin/node viewer.js -c "$ARKIMEDIR/etc/config.ini" --host "$ARKIME_HOSTNAME" >> "$ARKIMEDIR/logs/viewer.log" 2>&1
        popd > /dev/null
    fi
}

# Main execution
log "Starting Arkime services..."
wait_for_opensearch
initialize_arkime
service cron start
configure_suricata
configure_proxy
configure_wise
start_capture
start_viewer

log "Arkime services started successfully"