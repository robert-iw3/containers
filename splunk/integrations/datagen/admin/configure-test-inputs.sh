#!/usr/bin/env bash
# Configure a Splunk instance to receive test data, then remove that
# configuration again.
#
# Everything lands in one app, so teardown is deleting one directory. Nothing
# is written to etc/system/local.
#
#   ./configure-test-inputs.sh --target podman:splunk-idx --index test   # dry run
#   APPLY=1 ./configure-test-inputs.sh --target podman:splunk-idx --index test
#   APPLY=1 ./configure-test-inputs.sh --target podman:splunk-idx --paths tcp,udp
#   APPLY=1 ./configure-test-inputs.sh --target podman:splunk-idx --disable
#
# Transports match discover.sh: local:<SPLUNK_HOME>, ssh:<user@host>,
# podman:<container>, docker:<container>.
#
# --paths selects which receivers to bring up, which is also how a
# misbehaving one gets isolated.
#
# HEC is enabled in splunk_httpinput, the app that owns it, rather than by
# declaring [http] here. That app ships a substantial [http] stanza --
# pipeline routing, dedicatedIoThreads, sslVersions -- and a partial stanza
# from another app overrides parts of it for no benefit.
#
# A caution recorded because it cost real time: on Splunk Enterprise 10.4.2
# build 33c3bf42cd73, splunkd segfaulted in CallbackRunnerThread about
# eighteen seconds after start, on three of six consecutive restarts. Two of
# those restarts had HEC enabled and one had no test inputs at all, so these
# inputs are not the cause. It appeared only during a run of rapid restarts,
# in the window where agent-management packages were still registering.
#
# So: after a restart, treat a missing listener as possibly this. Check for a
# crash log before concluding the configuration is wrong, and leave time
# between restarts.
#
# Security notes, because this opens listeners:
#
#   The HEC token is generated per run and printed once. It is not stored in
#   this repository.
#   HEC keeps SSL enabled, and the token is restricted to the test index.
#   The TCP and UDP ports are high and unprivileged, bound wherever the
#   instance binds. In a container with no published port that reaches no
#   further than the container network.
#   Nothing here is meant to stay enabled. Run --disable when finished.
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
PATHS="${PATHS:-hec,tcp,udp}"

while [ $# -gt 0 ]; do
    case "$1" in
        --target)  TARGET="${2:-}"; shift 2 ;;
        --index)   INDEX="${2:-}"; shift 2 ;;
        --app)     APP="${2:-}"; shift 2 ;;
        --paths)   PATHS="${2:-}"; shift 2 ;;
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
want() { case ",$PATHS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

[ "$APPLY" = "1" ] || echo "DRY RUN. Nothing will change. Re-run with APPLY=1."

for sel in $(printf '%s' "$PATHS" | tr ',' ' '); do
    case "$sel" in
        hec|tcp|udp) ;;
        *) echo "FAIL: unknown path '$sel'; choose from hec,tcp,udp" >&2; exit 2 ;;
    esac
done

# ------------------------------------------------------------- discovery

DISCOVER="$(dirname "$0")/../../lib/discover.sh"
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

report_ports() {
    if want hec; then
        hec_on=$(x "$T_SPLUNK_HOME/bin/splunk" btool inputs list http 2>/dev/null \
            | grep -cE '^disabled = 0' || true)
        printf '  HEC port %-6s enabled: %s\n' "$HEC_PORT" \
            "$([ "${hec_on:-0}" -gt 0 ] && echo yes || echo no)"
    fi
    for sel in tcp udp; do
        want "$sel" || continue
        case "$sel" in tcp) p="$TCP_PORT" ;; udp) p="$UDP_PORT" ;; esac
        # grep -c, not grep -q: under pipefail grep -q exits early, the
        # producer takes SIGPIPE and returns 141, and the status inverts.
        n=$(x "$T_SPLUNK_HOME/bin/splunk" btool inputs list 2>/dev/null \
            | grep -cE "^\[$sel://(0\.0\.0\.0:)?${p}\]" || true)
        printf '  %s port %-6s stanzas: %s\n' "$sel" "$p" "${n:-0}"
    done
}

# --------------------------------------------------------------- disable

if [ "$DISABLE" = "1" ]; then
    say "Remove $APP from $TARGET"
    if ! x test -d "$APPDIR" 2>/dev/null; then
        echo "  $APPDIR is not present; nothing to remove"
    else
        # Guarded: APPDIR is built from a discovered SPLUNK_HOME and a fixed
        # app name, and both are asserted non-empty before anything is
        # removed, so this cannot widen to a parent directory.
        if [ -z "$T_SPLUNK_HOME" ] || [ -z "$APP" ] || [ "$APPDIR" = "/" ]; then
            echo "FAIL: refusing to remove an unsafe path: '$APPDIR'" >&2; exit 1
        fi
        run x rm -rf -- "$APPDIR"
        echo "  removed $APPDIR"
    fi
    if [ "$RESTART" = "1" ]; then
        say "Restart splunkd so the listeners close"
        run x "$T_SPLUNK_HOME/bin/splunk" restart --answer-yes
    else
        echo "  restart skipped; listeners stay open until splunkd restarts"
    fi
    say "Verify"
    if [ "$APPLY" = "1" ]; then
        PATHS=hec,tcp,udp report_ports
    fi
    exit 0
fi

# ---------------------------------------------------------------- enable

[ -n "$INDEX" ] || { echo "FAIL: --index is required; test data needs somewhere to land" >&2; exit 2; }

say "Paths selected: $PATHS"
if want hec && [ "$T_ROLE" = "forwarder" ]; then
    echo "  NOTE: HEC requires a full Splunk instance; this target is a forwarder." >&2
fi

say "Check the index exists"
idx_defined=$(x "$T_SPLUNK_HOME/bin/splunk" btool indexes list 2>/dev/null \
    | grep -cx "\[$INDEX\]" || true)
if [ "${idx_defined:-0}" -gt 0 ]; then
    echo "  index $INDEX is defined"
else
    echo "  WARNING: index $INDEX is not defined on this instance."
    echo "           Events for an index that does not exist are rejected."
    echo "           Define it first, in its own app, not in etc/system/local."
fi

if want hec && [ -z "$TOKEN" ]; then
    if [ -r /proc/sys/kernel/random/uuid ]; then
        TOKEN="$(cat /proc/sys/kernel/random/uuid)"
    else
        TOKEN="$(python3 -c 'import uuid;print(uuid.uuid4())')"
    fi
fi

WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT

{
  echo "# Test receivers for datagen. Temporary: remove this app when finished."
  echo "#"
  echo "# Created by admin/configure-test-inputs.sh. Every stanza names its"
  echo "# source type and index explicitly, so a routing test does not depend"
  echo "# on source type autodetection."
  echo "# Paths configured: $PATHS"
  if want hec; then
    echo ""
    echo "# The token stanza only. [http] itself is enabled in"
    echo "# splunk_httpinput, the app that owns it, so its routing, thread"
    echo "# and TLS settings are not partially overridden from here."
    echo "[http://datagen]"
    echo "disabled = 0"
    echo "token = $TOKEN"
    echo "index = $INDEX"
    echo "indexes = $INDEX"
    echo "sourcetype = datagen:hec"
  fi
  if want tcp; then
    echo ""
    echo "# Newline-framed events. The input sets the source type, because a"
    echo "# plain TCP stream carries no metadata of its own."
    echo "[tcp://$TCP_PORT]"
    echo "disabled = 0"
    echo "index = $INDEX"
    echo "sourcetype = datagen:tcp"
    echo "connection_host = ip"
  fi
  if want udp; then
    echo ""
    echo "# A datagram over maxEventSize is truncated on arrival. XML event"
    echo "# sources exceed the 1024 byte default, so this is raised to keep"
    echo "# a Windows event log or Sysmon event intact over UDP."
    echo "[udp://$UDP_PORT]"
    echo "disabled = 0"
    echo "index = $INDEX"
    echo "sourcetype = datagen:udp"
    echo "connection_host = ip"
    echo "maxEventSize = 8192"
  fi
} > "$WORK/inputs.conf"

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

if want hec; then
    # HEC is turned on in the app that owns it. splunk_httpinput ships a
    # substantial [http] stanza; setting only disabled and the port here
    # leaves its routing, thread and TLS settings intact.
    say "Enable HEC in splunk_httpinput (the app that owns [http])"
    HEC_APPDIR="$T_SPLUNK_HOME/etc/apps/splunk_httpinput"
    if ! x test -d "$HEC_APPDIR" 2>/dev/null; then
        echo "  WARNING: splunk_httpinput is not present on this instance."
        echo "           Enable HEC through the UI or the REST API instead;"
        echo "           declaring [http] from another app is what crashed"
        echo "           splunkd on 10.4.2."
    else
        printf '# Enabled for datagen testing. Revert by removing this file.\n[http]\ndisabled = 0\nport = %s\n' \
            "$HEC_PORT" > "$WORK/httpinput.conf"
        run x mkdir -p "$HEC_APPDIR/local"
        # Recorded so teardown knows this file is ours to remove.
        run cpin "$WORK/httpinput.conf" "$HEC_APPDIR/local/inputs.conf"
        echo "  wrote $HEC_APPDIR/local/inputs.conf"
    fi
fi

if [ "$RESTART" = "1" ]; then
    say "Restart splunkd so the listeners open"
    run x "$T_SPLUNK_HOME/bin/splunk" restart --answer-yes
else
    echo "  restart skipped; inputs apply on the next restart"
fi

say "Verify"
if [ "$APPLY" = "1" ]; then
    report_ports
    # A listener that is configured but absent usually means splunkd did not
    # come back. Report the crash count so that is distinguishable from the
    # configuration being wrong.
    running=$(x "$T_SPLUNK_HOME/bin/splunk" status 2>/dev/null \
        | grep -c 'splunkd is running' || true)
    printf '  splunkd running after restart: %s\n' \
        "$([ "${running:-0}" -gt 0 ] && echo yes || echo 'NO -- check for a crash log')"
    crashes=$(x sh -c "ls $T_SPLUNK_HOME/var/log/splunk/crash-*.log 2>/dev/null | wc -l" || true)
    printf '  crash logs present: %s\n' "${crashes:-unknown}"
    echo
    echo "  Destinations for emit.py, from a host that can reach this instance:"
    if want hec; then
        echo "    HEC token, shown once and not stored in this repository:"
        echo "      hec://$TOKEN@<host>:$HEC_PORT"
    fi
    want tcp && echo "      tcp://<host>:$TCP_PORT"
    want udp && echo "      udp://<host>:$UDP_PORT"
    echo
    echo "  Probe before sending:"
    echo "    ./emit.py --to '<destination>' --index $INDEX --preflight"
    echo
    echo "  Remove all of it when finished:"
    echo "    APPLY=1 $0 --target $TARGET --disable"
else
    echo "  dry run: nothing to verify"
fi
