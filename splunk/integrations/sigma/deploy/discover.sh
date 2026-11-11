#!/usr/bin/env bash
# Discover facts about a Splunk endpoint. Emits shell-sourceable variables.
#
# Knows nothing about any particular environment. Everything printed was
# read from the endpoint; nothing is defaulted or inferred from a naming
# convention. Where a fact cannot be established the variable is emitted
# empty, so a caller can tell "absent" from "not looked for".
#
# Read-only throughout: filesystem reads, btool, and splunk version. No
# search, so no login is required and nothing is written.
#
#   ./discover.sh --target podman:splunk-uf
#   ./discover.sh --target ssh:splunk@idx01.example.com --prefix IDX
#   ./discover.sh --logs local --sources /var/log/audit/audit.log,/var/log/secure
#   ./discover.sh --target local:/opt/splunk --json
#
# Transports: local:<SPLUNK_HOME or ->, ssh:<user@host>, podman:<container>,
# docker:<container>.
set -uo pipefail

TARGET=""
LOGS_AT=""
SOURCES=""
PREFIX=""
HOME_OVERRIDE=""
RUNTIME=""
AS_JSON=0

while [ $# -gt 0 ]; do
    case "$1" in
        --target)  TARGET="${2:-}"; shift 2 ;;
        --logs)    LOGS_AT="${2:-}"; shift 2 ;;
        --sources) SOURCES="${2:-}"; shift 2 ;;
        --prefix)  PREFIX="${2:-}"; shift 2 ;;
        --home)    HOME_OVERRIDE="${2:-}"; shift 2 ;;
        --runtime) RUNTIME="${2:-}"; shift 2 ;;
        --json)    AS_JSON=1; shift ;;
        -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$TARGET" ] && [ -z "$LOGS_AT" ]; then
    echo "FAIL: one of --target or --logs is required" >&2; exit 2
fi

KIND="${TARGET%%:*}"
WHERE="${TARGET#*:}"
# The container runtime is taken from the transport rather than assumed.
case "$KIND" in
    podman|docker) RUNTIME="${RUNTIME:-$KIND}" ;;
esac

declare -A F=()

emit() { F["$1"]="${2:-}"; }

# --------------------------------------------------------------- transport

x() {  # run a command at the target
    case "$KIND" in
        local) "$@" ;;
        ssh)   ssh -o BatchMode=yes -o ConnectTimeout=10 "$WHERE" "$@" ;;
        podman|docker) "$RUNTIME" exec "$WHERE" "$@" ;;
        *) return 127 ;;
    esac
}

xsh() { # run a shell snippet at the target
    case "$KIND" in
        local) sh -c "$1" ;;
        ssh)   ssh -o BatchMode=yes -o ConnectTimeout=10 "$WHERE" "$1" ;;
        podman|docker) "$RUNTIME" exec "$WHERE" sh -c "$1" ;;
        *) return 127 ;;
    esac
}

# Same, but as the service account. Every splunk CLI call on these images
# attempts "chown -R <caller> $SPLUNK_HOME", so running one as the wrong
# account rewrites ownership and stops splunkd. SERVICE_USER is established
# by a plain stat before any CLI call is made.
xsh_svc() {
    local u="${F[SERVICE_USER]:-}"
    case "$KIND" in
        local) if [ -n "$u" ] && [ "$u" != "$(id -un)" ]; then
                   sudo -n -u "$u" sh -c "$1"
               else sh -c "$1"; fi ;;
        ssh)   ssh -o BatchMode=yes -o ConnectTimeout=10 "$WHERE" "$1" ;;
        podman|docker)
               if [ -n "$u" ]; then "$RUNTIME" exec -u "$u" "$WHERE" sh -c "$1"
               else "$RUNTIME" exec "$WHERE" sh -c "$1"; fi ;;
        *) return 127 ;;
    esac
}

lx() { # run a shell snippet at a log location
    case "${LOGS_AT%%:*}" in
        local) sh -c "$1" ;;
        ssh)   ssh -o BatchMode=yes -o ConnectTimeout=10 "${LOGS_AT#*:}" "$1" ;;
        podman|docker) "${RUNTIME:-podman}" exec "${LOGS_AT#*:}" sh -c "$1" ;;
        *) return 127 ;;
    esac
}

# ------------------------------------------------------- endpoint discovery

discover_target() {
    emit TRANSPORT "$KIND"
    emit LOCATION  "$WHERE"
    emit REACHABLE 0

    if ! xsh 'exit 0' >/dev/null 2>&1; then
        emit ERROR "endpoint not reachable over $KIND"
        return
    fi
    emit REACHABLE 1

    # SPLUNK_HOME, asked for rather than assumed. The images export it; a
    # package install puts the binary on PATH; otherwise look for it.
    local home=""
    if [ -n "$HOME_OVERRIDE" ]; then
        home="$HOME_OVERRIDE"
    elif [ "$KIND" = "local" ] && [ "$WHERE" != "-" ] && [ -x "$WHERE/bin/splunk" ]; then
        home="$WHERE"
    else
        home="$(xsh 'printenv SPLUNK_HOME 2>/dev/null' 2>/dev/null | tr -d '\r')"
        if [ -z "$home" ]; then
            local bin
            bin="$(xsh 'command -v splunk 2>/dev/null' 2>/dev/null | tr -d '\r')"
            if [ -n "$bin" ]; then
                home="$(xsh "readlink -f '$bin' 2>/dev/null | sed 's|/bin/splunk$||'" 2>/dev/null | tr -d '\r')"
            fi
        fi
        if [ -z "$home" ]; then
            home="$(xsh 'find / -maxdepth 3 -type f -path "*/bin/splunk" 2>/dev/null | head -1 | sed "s|/bin/splunk$||"' 2>/dev/null | tr -d '\r')"
        fi
    fi
    emit SPLUNK_HOME "$home"
    if [ -z "$home" ]; then
        emit ERROR "no splunk installation found"
        return
    fi
    if ! xsh "test -x '$home/bin/splunk'" >/dev/null 2>&1; then
        emit ERROR "no splunk binary at $home/bin/splunk"
        return
    fi

    # The account splunkd runs as, established before any CLI call. var/ is
    # authoritative: splunkd must write its pid file there.
    emit SERVICE_USER  "$(xsh "stat -c '%U' '$home/var' 2>/dev/null" 2>/dev/null | tr -d '\r')"
    emit SERVICE_GROUP "$(xsh "stat -c '%G' '$home/var' 2>/dev/null" 2>/dev/null | tr -d '\r')"
    if [ "$KIND" = "podman" ] || [ "$KIND" = "docker" ]; then
        emit CONTAINER_USER "$("$RUNTIME" inspect "$WHERE" --format '{{.Config.User}}' 2>/dev/null)"
    fi

    # Version and product from the shipped manifest rather than CLI output:
    # a file read writes nothing, and PRODUCT names the role exactly.
    local vf
    vf="$(xsh "cat '$home/etc/splunk.version' 2>/dev/null" 2>/dev/null | tr -d '\r')"
    emit VERSION "$(printf '%s\n' "$vf" | sed -nE 's/^VERSION=//p' | head -1)"
    emit BUILD   "$(printf '%s\n' "$vf" | sed -nE 's/^BUILD=//p' | head -1)"
    emit PRODUCT "$(printf '%s\n' "$vf" | sed -nE 's/^PRODUCT=//p' | head -1)"
    emit PLATFORM "$(printf '%s\n' "$vf" | sed -nE 's/^PLATFORM=//p' | head -1)"

    # PRODUCT reads "splunk" on a universal forwarder too, so it cannot
    # distinguish the role. These two paths can: the web app tree ships only
    # with a full instance, and the SplunkUniversalForwarder app only with a
    # forwarder.
    emit ROLE ""
    if xsh "test -d '$home/share/splunk/search_mrsparkle'" >/dev/null 2>&1; then
        emit ROLE full
    elif xsh "test -d '$home/etc/apps/SplunkUniversalForwarder'" >/dev/null 2>&1; then
        emit ROLE forwarder
    fi

    # Liveness from the pid file, so no CLI call is needed to answer it.
    emit RUNNING 0
    if xsh "p=\$(cat '$home/var/run/splunk/splunkd.pid' 2>/dev/null | head -1); test -n \"\$p\" && test -d /proc/\$p" >/dev/null 2>&1; then
        emit RUNNING 1
    fi

    # Installed apps, and whether the pieces this integration cares about
    # are already present.
    local apps
    apps="$(xsh "ls -1 '$home/etc/apps' 2>/dev/null" 2>/dev/null | tr -d '\r' | tr '\n' ',' | sed 's/,$//')"
    emit APPS "$apps"
    emit APP_COUNT "$(printf '%s' "$apps" | tr ',' '\n' | grep -c . || true)"
    for probe in Splunk_TA_nix Splunk_SA_CIM; do
        local present=0
        printf '%s' "$apps" | tr ',' '\n' | grep -qx "$probe" && present=1
        emit "HAS_${probe}" "$present"
    done

    # Indexes and forwarding, read with btool so no login is needed.
    emit INDEXES "$(xsh_svc "'$home/bin/splunk' btool indexes list 2>/dev/null | sed -n 's/^\[\(.*\)\]$/\1/p' | sort | tr '\n' ',' | sed 's/,\$//'" 2>/dev/null | tr -d '\r')"
    emit OUTPUT_SERVERS "$(xsh_svc "'$home/bin/splunk' btool outputs list 2>/dev/null | sed -nE 's/^server[[:space:]]*=[[:space:]]*//p' | tr '\n' ',' | sed 's/,\$//'" 2>/dev/null | tr -d '\r')"
    emit RECEIVING_PORTS "$(xsh_svc "'$home/bin/splunk' btool inputs list 2>/dev/null | sed -nE 's/^\[splunktcp(-ssl)?:\/\/(.*)\]$/\2/p' | tr '\n' ',' | sed 's/,\$//'" 2>/dev/null | tr -d '\r')"

    # btool check as a configuration baseline, so a caller can diff later.
    emit BTOOL_CHECK_LINES "$(xsh_svc "'$home/bin/splunk' btool check 2>&1 | grep -c . || true" 2>/dev/null | tr -d '\r')"

    # Can this endpoint see a host filesystem, or only its own? Decides
    # whether log content has to be copied in.
    emit IS_CONTAINER 0
    case "$KIND" in podman|docker) emit IS_CONTAINER 1 ;; esac
}

# ----------------------------------------------------------- log discovery

discover_logs() {
    emit LOGS_TRANSPORT "${LOGS_AT%%:*}"
    emit LOGS_LOCATION  "${LOGS_AT#*:}"
    if [ -z "$SOURCES" ]; then
        emit ERROR "--logs needs --sources; the operator declares which paths are in scope"
        return
    fi
    local found=() missing=() unreadable=()
    local IFS_SAVE="$IFS"; IFS=','
    for entry in $SOURCES; do
        IFS="$IFS_SAVE"
        local path="${entry%%:*}"
        if lx "test -e '$path'" >/dev/null 2>&1; then
            if lx "test -r '$path'" >/dev/null 2>&1; then
                local size
                size="$(lx "stat -c%s '$path' 2>/dev/null" 2>/dev/null | tr -d '\r')"
                found+=("${path}:${size:-0}")
            else
                unreadable+=("$path")
            fi
        else
            missing+=("$path")
        fi
        IFS=','
    done
    IFS="$IFS_SAVE"
    emit LOGS_READABLE   "$(printf '%s,' "${found[@]:-}" | sed 's/,$//')"
    emit LOGS_UNREADABLE "$(printf '%s,' "${unreadable[@]:-}" | sed 's/,$//')"
    emit LOGS_MISSING    "$(printf '%s,' "${missing[@]:-}" | sed 's/,$//')"

    # auditd state at the log location, since an auditd log with no policy
    # loaded contains almost nothing a detection can match.
    emit AUDITD_PRESENT 0
    lx 'command -v auditctl >/dev/null 2>&1' >/dev/null 2>&1 && emit AUDITD_PRESENT 1
    emit AUDITD_ACTIVE 0
    if lx 'systemctl is-active auditd 2>/dev/null | grep -qx active' >/dev/null 2>&1; then
        emit AUDITD_ACTIVE 1
    fi
    # Count execve records, which is what most auditd detection content needs.
    local al="${SOURCES%%:*}"
    for entry in $(printf '%s' "$SOURCES" | tr ',' ' '); do
        case "$entry" in */audit.log*) al="${entry%%:*}" ;; esac
    done
    if lx "test -r '$al'" >/dev/null 2>&1; then
        emit AUDIT_EXECVE_RECORDS "$(lx "grep -c '^type=EXECVE' '$al' 2>/dev/null || true" 2>/dev/null | tr -d '\r')"
        emit AUDIT_TOTAL_RECORDS  "$(lx "grep -c '^type=' '$al' 2>/dev/null || true" 2>/dev/null | tr -d '\r')"
    fi
}

[ -n "$TARGET" ]  && discover_target
[ -n "$LOGS_AT" ] && discover_logs

# ------------------------------------------------------------------ output

P=""
[ -n "$PREFIX" ] && P="${PREFIX}_"

if [ "$AS_JSON" = "1" ]; then
    printf '{\n'
    first=1
    for k in $(printf '%s\n' "${!F[@]}" | sort); do
        [ "$first" = "1" ] || printf ',\n'
        first=0
        printf '  "%s%s": "%s"' "$P" "$k" "$(printf '%s' "${F[$k]}" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    done
    printf '\n}\n'
else
    echo "# Discovered $(date -u +%Y-%m-%dT%H:%M:%SZ). Facts only; empty means not established."
    for k in $(printf '%s\n' "${!F[@]}" | sort); do
        printf '%s%s=%s\n' "$P" "$k" "$(printf '%q' "${F[$k]}")"
    done
fi

[ -n "${F[ERROR]:-}" ] && exit 1
exit 0
