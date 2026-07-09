#!/bin/bash
# ==============================================================================
# entrypoint.sh -- Suricata IDS/IPS container entrypoint
#
# Responsibilities:
#   1. Resolve every tunable from the environment (with safe defaults).
#   2. Render /etc/suricata/suricata.yaml from the mounted template.
#   3. Configure the data plane for the selected mode:
#        IPS_MODE=ids                      -> passive af-packet capture
#        IPS_MODE=ips INLINE_METHOD=afpacket_bridge -> two-NIC inline bridge
#        IPS_MODE=ips INLINE_METHOD=nfqueue          -> NFQUEUE inline
#   4. Validate the config (suricata -T) before launching.
#   5. Drop to the unprivileged 'suricata' user when capabilities allow.
#
# Everything is environment-agnostic; nothing here hardcodes a network.
# ==============================================================================
set -eu
[ "${TRACE:-}" != "" ] && set -x

log() { echo "[entrypoint] $*"; }
warn() { echo "[entrypoint] WARN: $*" >&2; }
die() { echo "[entrypoint] ERROR: $*" >&2; exit 1; }

# ------------------------------------------------------------------------------
# 0. Defaults -- every template token gets a value here so an unset env var still
#    yields a valid config. Override any of these via -e / compose environment.
# ------------------------------------------------------------------------------
: "${IPS_MODE:=ids}"                       # ids | ips
: "${INLINE_METHOD:=afpacket_bridge}"      # afpacket_bridge | nfqueue

: "${HOME_NET:=[10.0.0.0/8,172.16.0.0/12,192.168.0.0/16]}"
: "${K8S_API:=\$HOME_NET}"                 # literal $HOME_NET unless overridden
: "${DOCKER_HOSTS:=\$HOME_NET}"

: "${CAPTURE_INTERFACE:=eth0}"
: "${BRIDGE_IFACE_B:=eth1}"

: "${AF_THREADS:=auto}"
: "${AF_CLUSTER_ID_A:=98}"
: "${AF_CLUSTER_ID_B:=97}"
: "${AF_DEFRAG:=no}"
: "${AF_RING_SIZE:=65536}"
: "${AF_BUFFER_SIZE:=65535}"

: "${NFQUEUE_NUM:=0}"
: "${NFQUEUE_COUNT:=4}"
: "${NFQ_MODE:=repeat}"
: "${NFQ_BATCHCOUNT:=20}"
: "${NFQ_FAIL_OPEN:=no}"
: "${NFQUEUE_CHAINS:=FORWARD}"             # space/comma list: INPUT OUTPUT FORWARD
: "${MANAGE_IPTABLES:=yes}"                # let entrypoint add/remove NFQUEUE rules

: "${EXCEPTION_POLICY:=auto}"              # auto=fail-closed; ignore=fail-open
: "${STREAM_INLINE:=auto}"
: "${FILESTORE_ENABLED:=no}"
: "${JA3_ENABLED:=yes}"
: "${EVE_ALERT_PAYLOAD:=no}"
: "${EVE_ALERT_PACKET:=no}"
: "${LOG_LEVEL:=notice}"

: "${DETECT_PROFILE:=medium}"
: "${MPM_ALGO:=hs}"
: "${SPM_ALGO:=hs}"
: "${CPU_AFFINITY:=no}"
: "${WORKER_CPUS:=all}"
: "${FLOW_MEMCAP:=256mb}"
: "${STREAM_MEMCAP:=256mb}"
: "${REASSEMBLY_MEMCAP:=512mb}"
: "${RUNMODE:=workers}"
: "${MAX_PENDING_PACKETS:=4096}"

: "${RULE_ACTION_POLICY:=balanced}"        # passthrough to toggle script (see below)
: "${DISABLE_OFFLOAD:=yes}"                # ethtool -K off for bridge correctness
: "${SURICATA_TEST_CONFIG:=yes}"           # run suricata -T before launch

# AF copy-mode is derived from the run mode: 'ids' = passive, 'ips' = forward+block.
if [ "$IPS_MODE" = "ips" ] && [ "$INLINE_METHOD" = "afpacket_bridge" ]; then
    AF_COPY_MODE="ips"
else
    AF_COPY_MODE="ids"
fi

# ------------------------------------------------------------------------------
# 1. Seed /etc/suricata from the baked-in dist copy on first run (volume mounts
#    may start empty). Preserves the original behaviour.
# ------------------------------------------------------------------------------
if [ -d /etc/suricata.dist ]; then
    for src in /etc/suricata.dist/*; do
        dst="/etc/suricata/$(basename "$src")"
        [ -e "$dst" ] || { log "Seeding $dst"; cp -a "$src" "$dst"; }
    done
fi
mkdir -p /etc/suricata/data /var/lib/suricata/rules /var/log/suricata /var/run/suricata

# Ensure dataset files exist (empty is valid; rules using them just won't match).
for ds in bad_ips.lst bad_domains.lst bad_sni.lst bad_ja3.lst bad_file_md5.lst; do
    [ -f "/etc/suricata/data/$ds" ] || : > "/etc/suricata/data/$ds"
done

# ------------------------------------------------------------------------------
# 2. Render suricata.yaml from the template.
#    Template is searched in mount locations first, then the image default.
# ------------------------------------------------------------------------------
TEMPLATE=""
for cand in /etc/suricata/templates/suricata.yaml.template \
            /etc/suricata/suricata.yaml.template \
            /usr/local/share/suricata/suricata.yaml.template; do
    [ -f "$cand" ] && { TEMPLATE="$cand"; break; }
done

render_config() {
    local out=/etc/suricata/suricata.yaml
    log "Rendering $out from $TEMPLATE (mode=$IPS_MODE/$INLINE_METHOD)…"
    # sed-based token substitution. Using @@TOKEN@@ avoids clobbering Suricata's
    # own $HOME_NET / $EXTERNAL_NET self-references in the output.
    local tmp; tmp="$(mktemp)"
    cp "$TEMPLATE" "$tmp"
    local vars="HOME_NET K8S_API DOCKER_HOSTS CAPTURE_INTERFACE BRIDGE_IFACE_B \
        AF_THREADS AF_CLUSTER_ID_A AF_CLUSTER_ID_B AF_DEFRAG AF_RING_SIZE \
        AF_BUFFER_SIZE AF_COPY_MODE NFQ_MODE NFQ_BATCHCOUNT NFQ_FAIL_OPEN \
        EXCEPTION_POLICY STREAM_INLINE FILESTORE_ENABLED JA3_ENABLED \
        EVE_ALERT_PAYLOAD EVE_ALERT_PACKET LOG_LEVEL DETECT_PROFILE MPM_ALGO \
        SPM_ALGO CPU_AFFINITY WORKER_CPUS FLOW_MEMCAP STREAM_MEMCAP \
        REASSEMBLY_MEMCAP RUNMODE MAX_PENDING_PACKETS"
    for v in $vars; do
        # Escape sed-special chars in the value.
        local val; val="$(printf '%s' "${!v}" | sed -e 's/[&/\]/\\&/g')"
        sed -i "s/@@${v}@@/${val}/g" "$tmp"
    done
    # Fail loudly if any token was left unrendered.
    if grep -q '@@[A-Z_]*@@' "$tmp"; then
        warn "Unrendered tokens remain:"; grep -oE '@@[A-Z_]+@@' "$tmp" | sort -u >&2
        die "Template rendering incomplete."
    fi
    install -m 0640 "$tmp" "$out"; rm -f "$tmp"
    log "Config rendered."
}

if [ -n "$TEMPLATE" ]; then
    render_config
elif [ -f /etc/suricata/suricata.yaml ]; then
    warn "No template found; using existing /etc/suricata/suricata.yaml as-is."
else
    die "No template and no suricata.yaml present."
fi

# ------------------------------------------------------------------------------
# 3. Apply the risk-based rule action policy (alert vs drop per tier).
#    The toggle script decides which tiers are 'drop' vs 'alert' based on
#    RULE_ACTION_POLICY and the live IPS_MODE.
# ------------------------------------------------------------------------------
if command -v toggle_rule_blocking.py >/dev/null 2>&1; then
    log "Applying rule action policy: $RULE_ACTION_POLICY (ips_mode=$IPS_MODE)"
    toggle_rule_blocking.py --policy "$RULE_ACTION_POLICY" --ips-mode "$IPS_MODE" \
        --rules-dir /var/lib/suricata/rules || warn "toggle script returned non-zero."
fi

# ------------------------------------------------------------------------------
# 4. Data-plane setup per mode.
#    Helper functions are defined first so they exist when the dispatch calls them.
# ------------------------------------------------------------------------------
disable_offload() {
    local ifc="$1"
    [ "$DISABLE_OFFLOAD" = "yes" ] || return 0
    command -v ethtool >/dev/null 2>&1 || { warn "ethtool absent; cannot disable offload on $ifc"; return 0; }
    # GRO/LRO/TSO/GSO create super-MTU frames that break inline copy/forwarding.
    ethtool -K "$ifc" gro off lro off tso off gso off 2>/dev/null \
        && log "Disabled NIC offload on $ifc" \
        || warn "Could not fully disable offload on $ifc (may need NET_ADMIN)."
}

# NFQUEUE iptables management
setup_nfqueue_iptables() {
    command -v iptables >/dev/null 2>&1 || { warn "iptables absent; skipping rule setup."; return 0; }
    local qspec
    if [ "$NFQUEUE_COUNT" -gt 1 ]; then
        qspec="--queue-balance ${NFQUEUE_NUM}:$((NFQUEUE_NUM+NFQUEUE_COUNT-1))"
    else
        qspec="--queue-num ${NFQUEUE_NUM}"
    fi
    # queue-bypass = fail-open at the netfilter layer (no Suricata -> ACCEPT).
    local bypass=""
    [ "$NFQ_FAIL_OPEN" = "yes" ] && bypass="--queue-bypass"
    local chains; chains="$(echo "$NFQUEUE_CHAINS" | tr ',' ' ')"
    for ch in $chains; do
        # 'repeat' mode marks reinjected packets so they skip re-queue.
        if [ "$NFQ_MODE" = "repeat" ]; then
            iptables -t mangle -C "$ch" -m mark --mark 1/1 -j ACCEPT 2>/dev/null \
                || iptables -t mangle -I "$ch" -m mark --mark 1/1 -j ACCEPT
            iptables -t mangle -C "$ch" -j NFQUEUE $qspec $bypass 2>/dev/null \
                || iptables -t mangle -A "$ch" -j NFQUEUE $qspec $bypass
        else
            iptables -C "$ch" -j NFQUEUE $qspec $bypass 2>/dev/null \
                || iptables -I "$ch" -j NFQUEUE $qspec $bypass
        fi
        log "NFQUEUE iptables rule ensured on $ch ($qspec ${bypass:-no-bypass})."
    done
    # Clean up our rules on exit so the host isn't left filtering through a dead queue.
    trap 'teardown_nfqueue_iptables' EXIT INT TERM
}

teardown_nfqueue_iptables() {
    command -v iptables >/dev/null 2>&1 || return 0
    local chains; chains="$(echo "$NFQUEUE_CHAINS" | tr ',' ' ')"
    for ch in $chains; do
        if [ "$NFQ_MODE" = "repeat" ]; then
            iptables -t mangle -D "$ch" -j NFQUEUE --queue-balance "${NFQUEUE_NUM}:$((NFQUEUE_NUM+NFQUEUE_COUNT-1))" 2>/dev/null || true
            iptables -t mangle -D "$ch" -m mark --mark 1/1 -j ACCEPT 2>/dev/null || true
        else
            iptables -D "$ch" -j NFQUEUE 2>/dev/null || true
        fi
    done
    log "NFQUEUE iptables rules removed."
}

SURI_ARGS=""
case "$IPS_MODE" in
    ids)
        log "Mode: IDS (passive) on $CAPTURE_INTERFACE"
        SURI_ARGS="--af-packet=$CAPTURE_INTERFACE"
        ;;
    ips)
        case "$INLINE_METHOD" in
            afpacket_bridge)
                log "Mode: IPS af-packet bridge  $CAPTURE_INTERFACE <-> $BRIDGE_IFACE_B"
                disable_offload "$CAPTURE_INTERFACE"
                disable_offload "$BRIDGE_IFACE_B"
                # Bring both legs up in promiscuous mode (no IP needed for a bridge tap).
                for ifc in "$CAPTURE_INTERFACE" "$BRIDGE_IFACE_B"; do
                    ip link set "$ifc" up promisc on 2>/dev/null || warn "Could not set $ifc up/promisc."
                done
                SURI_ARGS="--af-packet"
                ;;
            nfqueue)
                log "Mode: IPS NFQUEUE  queues ${NFQUEUE_NUM}..$((NFQUEUE_NUM+NFQUEUE_COUNT-1)) on chains: $NFQUEUE_CHAINS"
                # Build one -q per queue.
                local_q=$NFQUEUE_NUM
                end_q=$((NFQUEUE_NUM + NFQUEUE_COUNT - 1))
                while [ "$local_q" -le "$end_q" ]; do
                    SURI_ARGS="$SURI_ARGS -q $local_q"
                    local_q=$((local_q + 1))
                done
                if [ "$MANAGE_IPTABLES" = "yes" ]; then
                    setup_nfqueue_iptables
                fi
                ;;
            *) die "Unknown INLINE_METHOD '$INLINE_METHOD' (afpacket_bridge|nfqueue)." ;;
        esac
        ;;
    *) die "Unknown IPS_MODE '$IPS_MODE' (ids|ips)." ;;
esac

# ------------------------------------------------------------------------------
# 5. Update rules and validate config.
# ------------------------------------------------------------------------------
if [ "${SURICATA_UPDATE:-yes}" = "yes" ]; then
    log "Refreshing managed ruleset (suricata-update)…"
    suricata-update --no-test --no-reload 2>/dev/null || warn "suricata-update failed (offline?); using existing rules."
fi

if [ "$SURICATA_TEST_CONFIG" = "yes" ]; then
    log "Validating configuration (suricata -T)…"
    if [ "$IPS_MODE" = "ips" ] && [ "$INLINE_METHOD" = "afpacket_bridge" ]; then
        suricata -T -c /etc/suricata/suricata.yaml --af-packet 2>&1 | tail -5 || die "Config validation failed."
    else
        suricata -T -c /etc/suricata/suricata.yaml 2>&1 | tail -5 || die "Config validation failed."
    fi
    log "Configuration valid."
fi

# ------------------------------------------------------------------------------
# 6. Capability check + privilege drop.
# ------------------------------------------------------------------------------
run_as_user="yes"
have_cap() { getpcaps 1 2>&1 | grep -qi "$1"; }

for cap in net_admin net_raw; do
    if ! have_cap "$cap"; then warn "missing capability $cap (use --cap-add $cap)"; run_as_user="no"; fi
done
have_cap sys_nice || warn "missing sys_nice (scheduling priority); continuing."

fix_perms() {
    [ -n "${PGID:-}" ] && groupmod -o -g "$PGID" suricata 2>/dev/null || true
    [ -n "${PUID:-}" ] && usermod -o -u "$PUID" suricata 2>/dev/null || true
    chown -R suricata:suricata /etc/suricata /var/lib/suricata /var/log/suricata /var/run/suricata 2>/dev/null || true
}

USER_ARGS=""
if [ "$run_as_user" = "yes" ]; then
    fix_perms
    USER_ARGS="--user suricata --group suricata"
    log "Will drop privileges to suricata:suricata after socket setup."
else
    warn "Running as root due to missing capabilities."
fi

# ------------------------------------------------------------------------------
# 7. Exec Suricata.
# ------------------------------------------------------------------------------
if [ "$#" -gt 0 ] && [ "${1#-}" = "$1" ]; then
    exec "$@"
fi

log "Launching: suricata -c /etc/suricata/suricata.yaml --runmode $RUNMODE $SURI_ARGS $USER_ARGS $*"
exec /usr/bin/suricata \
    -c /etc/suricata/suricata.yaml \
    --runmode "$RUNMODE" \
    $SURI_ARGS \
    $USER_ARGS \
    "$@"