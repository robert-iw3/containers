#!/usr/bin/env bash
# Configure a Splunk instance to receive test data over every delivery path,
# then remove that configuration again.
#
# Everything lands in one app, so teardown is deleting one directory. Nothing
# is written to etc/system/local.
#
#   ./configure-test-inputs.sh --target podman:splunk-idx            # dry run
#   APPLY=1 ./configure-test-inputs.sh --target podman:splunk-idx
#   APPLY=1 ./configure-test-inputs.sh --target podman:splunk-idx --disable
#
# Transports match discover.sh: local:<SPLUNK_HOME>, ssh:<user@host>,
# podman:<container>, docker:<container>.
#
# Security notes, because this opens listeners:
#
#   The HEC token is generated per run and printed once. It is not stored in
#   this repository.
#   HEC keeps SSL enabled. The token is restricted to the test index.
#   The TCP and UDP ports are high and non-privileged, and bound wherever the
#   instance binds. In a container with no published port, that reaches no
#   further than the container network.
#   Nothing here is intended to stay enabled. Run --disable when finished.
set -euo pipefail

TARGET=""
APPLY="${APPLY:-0}"
DISABLE=0
APP="${APP:-datagen_test_inputs}"
INDEX="${INDEX:-}"
HEC_PORT="${HEC_PORT:-8088}"
TCP_PORT="${TCP_PORT:-11514}"
UDP_PORT="${UDP_PORT:-11515}"
TOKEN="${TOKEN:-}"
RESTART="${RESTART:-1}"
RUNTIME="${RUNTIME:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --target)  TARGET="${2:-}"; shift 2 ;;
        --index)   INDEX="${2:-}"; shift 2 ;;
        --app)     APP="${2:-}"; shift 2 ;;
        --disable) DISABLE=1; shift ;;
        --apply)   APPLY=1; shift ;;
        --no-restart) RESTART=0; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -n "$TARGET" ] || { echo "FAIL: --target <transport:location> is required" >&2; exit 2; }

KIND="${TARGET%%:*}"
WHERE="${TARGET#*:}"
case "$KIND" in podman|docker) RUNTIME="${RUNTIME:-$KIND}" ;; esac

say() { printf '\n== %s\n' "$*"; }
run() { if [ "$APPLY" = "1" ]; then "$@"; else printf '  [dry-run] %s\n' "$*"; fi; }

[ "$APPLY" = "1" ] || echo "DRY RUN. Nothing will change. Re-run with APPLY=1."

# ------------------------------------------------------------- discovery

# Reuse the discovery layer rather than assuming paths or accounts.
DISCOVER="$(dirname "$0")/../../sigma/deploy/discover.sh"
if [ ! -x "$DISCOVER" ]; then
    echo "FAIL: discover.sh not found at $DISCOVER" >&2; exit 1
fi

say "Discover the target"
eval "$("$DISCOVER" --target "$TARGET" --prefix T 2>/dev/null | grep -E '^T_')"
: "${T_SPLUNK_HOME:=}" "${T_SERVICE_USER:=}" "${T_ROLE:=}" "${T_RUNNING:=0}"
if [ -z "$T_SPLUNK_HOME" ]; then
    echo "FAIL: no Splunk installation discovered at $TARGET" >&2; exit 1
fi
printf '  home=%s role=%s account=%s running=%s\n' \
    "$T_SPLUNK_HOME" "${T_ROLE:-unknown}" "$T_SERVICE_USER" "$T_RUNNING"

if [ "$T_ROLE" = "forwarder" ]; then
    echo "  NOTE: this is a universal forwarder. It can receive on TCP and UDP," >&2
    echo "        but HEC and indexing require a full Splunk instance." >&2
fi

# The CLI chowns SPLUNK_HOME to whoever invokes it, so every call uses the
# discovered account.
x() {
    case "$KIND" in
        local) sudo -n -u "$T_SERVICE_USER" "$@" ;;
        ssh)   ssh -o BatchMode=yes "$WHERE" "$@" ;;
        podman|docker) "$RUNTIME" exec -u "$T_SERVICE_USER" "$WHERE" "$@" ;;
    esac
}
cpin() {
    case "$KIND" in
        local) cp "$1" "$2" ;;
        ssh)   scp -q -o BatchMode=yes "$1" "$WHERE:$2" ;;
        podman|docker) "$RUNTIME" cp "$1" "$WHERE:$2" ;;
    esac
}

APPDIR="$T_SPLUNK_HOME/etc/apps/$APP"

# --------------------------------------------------------------- disable

if [ "$DISABLE" = "1" ]; then
    say "Remove $APP from $TARGET"
    if ! x test -d "$APPDIR" 2>/dev/null; then
        echo "  $APPDIR is not present; nothing to remove"
    else
        run x rm -rf "$APPDIR"
        echo "  removed $APPDIR"
    fi
    if [ "$RESTART" = "1" ]; then
        say "Restart splunkd so the listeners close"
        run x "$T_SPLUNK_HOME/bin/splunk" restart --answer-yes
    else
        echo "  restart skipped; the listeners stay open until splunkd restarts"
    fi
    say "Verify"
    if [ "$APPLY" = "1" ]; then
        for p in "$HEC_PORT" "$TCP_PORT" "$UDP_PORT"; do
            n=$(x "$T_SPLUNK_HOME/bin/splunk" btool inputs list 2>/dev/null \
                | grep -cE "://(0.0.0.0:)?${p}\]" || true)
            printf '  port %-6s stanzas remaining: %s\n' "$p" "${n:-0}"
        done
    fi
    exit 0
fi

# ---------------------------------------------------------------- enable

[ -n "$INDEX" ] || { echo "FAIL: --index is required; test data needs somewhere to land" >&2; exit 2; }

say "Check the index exists"
# grep -c, not grep -q: under pipefail, grep -q exits early, the producer
# takes SIGPIPE and returns 141, and the pipeline status inverts the test.
idx_defined=$(x "$T_SPLUNK_HOME/bin/splunk" btool indexes list 2>/dev/null \
    | grep -cx "\[$INDEX\]" || true)
if [ "${idx_defined:-0}" -gt 0 ]; then
    echo "  index $INDEX is defined"
else
    echo "  WARNING: index $INDEX is not defined on this instance."
    echo "           HEC will reject events for an index that does not exist."
    echo "           Define it first, in its own app, not in etc/system/local."
fi

if [ -z "$TOKEN" ]; then
    # Prefer the kernel's generator; fall back to the shell's own randomness.
    if [ -r /proc/sys/kernel/random/uuid ]; then
        TOKEN="$(cat /proc/sys/kernel/random/uuid)"
    else
        TOKEN="$(python3 -c 'import uuid;print(uuid.uuid4())')"
    fi
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/inputs.conf" <<CONF
# Test receivers for datagen. Temporary: remove this app when finished.
#
# Created by admin/configure-test-inputs.sh. Every stanza names its source
# type and index explicitly, so a routing test is not at the mercy of
# source type autodetection.

[http]
disabled = 0
port = $HEC_PORT
enableSSL = 1

[http://datagen]
disabled = 0
token = $TOKEN
index = $INDEX
indexes = $INDEX
sourcetype = datagen:hec

# Newline-framed events. The input sets the source type, because a plain TCP
# stream carries no metadata of its own.
[tcp://$TCP_PORT]
disabled = 0
index = $INDEX
sourcetype = datagen:tcp
connection_host = ip

[udp://$UDP_PORT]
disabled = 0
index = $INDEX
sourcetype = datagen:udp
connection_host = ip
CONF

cat > "$WORK/app.conf" <<CONF
[install]
state = enabled

[ui]
is_visible = 0
label = datagen test inputs (temporary)

[package]
id = $APP
CONF

say "Install $APP"
run x mkdir -p "$APPDIR/local" "$APPDIR/metadata"
run cpin "$WORK/inputs.conf" "$APPDIR/local/inputs.conf"
run cpin "$WORK/app.conf" "$APPDIR/local/app.conf"
run x chmod 600 "$APPDIR/local/inputs.conf"

if [ "$RESTART" = "1" ]; then
    say "Restart splunkd so the listeners open"
    run x "$T_SPLUNK_HOME/bin/splunk" restart --answer-yes
else
    echo "  restart skipped; the inputs apply on the next restart"
fi

say "Verify"
if [ "$APPLY" = "1" ]; then
    for p in "$HEC_PORT" "$TCP_PORT" "$UDP_PORT"; do
        n=$(x "$T_SPLUNK_HOME/bin/splunk" btool inputs list 2>/dev/null \
            | grep -cE "://(0.0.0.0:)?${p}\]" || true)
        printf '  port %-6s configured: %s stanza(s)\n' "$p" "${n:-0}"
    done
    echo
    echo "  HEC token, shown once and not stored in this repository:"
    echo "    $TOKEN"
    echo
    echo "  Destinations for emit.py, from a host that can reach this instance:"
    echo "    hec://$TOKEN@<host>:$HEC_PORT"
    echo "    tcp://<host>:$TCP_PORT"
    echo "    udp://<host>:$UDP_PORT"
    echo
    echo "  Probe them before sending:"
    echo "    ./emit.py --to 'hec://$TOKEN@<host>:$HEC_PORT' --index $INDEX --preflight"
    echo
    echo "  Remove all of it when finished:"
    echo "    APPLY=1 $0 --target $TARGET --disable"
else
    echo "  dry run: nothing to verify"
fi
