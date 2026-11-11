#!/usr/bin/env bash
# Discover facts about a Splunk endpoint. Emits shell-sourceable variables.
#
# Knows nothing about any particular environment. Everything printed was read
# from the endpoint; nothing is defaulted or inferred from a naming
# convention. Where a fact cannot be established the variable is emitted
# empty, so a caller can tell "absent" from "not looked for".
#
# Read-only throughout: filesystem reads and btool. No search, so no login is
# needed and nothing is written.
#
#   ./discover.sh --target podman:splunk-uf
#   ./discover.sh --target ssh:splunk@idx01.example.com --prefix IDX
#   ./discover.sh --target k8s:splunk/splunk-idxc-0 --inputs
#   ./discover.sh --logs local --sources /var/log/audit/audit.log,/var/log/secure
#   ./discover.sh --target local:/opt/splunk --json
#
# --inputs answers a different question from the default: not "what is this
# instance" but "what can it receive, and what would stop data arriving".
# Each receiving path is reported with the settings that decide whether data
# lands where the operator expects, and anything missing is named as a
# finding with what to do about it. An input pointing at an index that does
# not exist, or with no source type set, drops or misfiles data without
# failing, which is the kind of thing worth being told before sending.
#
# Transports come from lib/splunk-transport.sh: local, ssh, podman, docker,
# and k8s.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=splunk-transport.sh
. "$HERE/splunk-transport.sh"

TARGET=""
LOGS_AT=""
SOURCES=""
PREFIX=""
HOME_OVERRIDE=""
AS_JSON=0
WANT_INPUTS=0
WANT_TRACE=0
HOP_MAP=""

while [ $# -gt 0 ]; do
    case "$1" in
        --target)  TARGET="${2:-}"; shift 2 ;;
        --logs)    LOGS_AT="${2:-}"; shift 2 ;;
        --sources) SOURCES="${2:-}"; shift 2 ;;
        --prefix)  PREFIX="${2:-}"; shift 2 ;;
        --home)    HOME_OVERRIDE="${2:-}"; shift 2 ;;
        --runtime) RUNTIME="${2:-}"; shift 2 ;;
        --kubectl) KUBECTL="${2:-}"; shift 2 ;;
        --inputs)  WANT_INPUTS=1; shift ;;
        --trace)   WANT_TRACE=1; WANT_INPUTS=1; shift ;;
        --map)     HOP_MAP="${2:-}"; shift 2 ;;
        --json)    AS_JSON=1; shift ;;
        -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$TARGET" ] && [ -z "$LOGS_AT" ]; then
    echo "FAIL: one of --target or --logs is required" >&2; exit 2
fi
if [ -n "$TARGET" ] && ! t_valid "$TARGET"; then
    echo "FAIL: unknown transport in '$TARGET'; substrates: $(t_substrates)" >&2
    exit 2
fi

declare -A F=()
FINDINGS=()

emit() { F["$1"]="${2:-}"; }
# A finding is something an operator has to act on, with what to do.
finding() { FINDINGS+=("$1|$2"); }

# Shorthands bound to this run's target.
sh_t()    { t_sh "$TARGET" "$1"; }
sh_svc()  { t_sh_as "$TARGET" "${F[SERVICE_USER]:-}" "$1"; }
sh_logs() { t_sh "$LOGS_AT" "$1"; }

trim() { tr -d '\r'; }

# ------------------------------------------------------- endpoint discovery

discover_target() {
    emit TRANSPORT "$(t_kind "$TARGET")"
    emit LOCATION  "$(t_where "$TARGET")"
    emit REACHABLE 0

    if ! t_check_tool "$TARGET"; then
        emit ERROR "$(t_required_tool "$TARGET") is not installed on this machine"
        finding "$(t_required_tool "$TARGET") is not on PATH" \
                "install it, or pick a transport this machine can use"
        return
    fi
    if ! t_reachable "$TARGET"; then
        emit ERROR "endpoint not reachable over $(t_kind "$TARGET")"
        finding "cannot reach $TARGET" \
                "check the host, container or pod exists and is running"
        return
    fi
    emit REACHABLE 1

    # SPLUNK_HOME, asked for rather than assumed.
    local home=""
    if [ -n "$HOME_OVERRIDE" ]; then
        home="$HOME_OVERRIDE"
    elif [ "$(t_kind "$TARGET")" = "local" ] && [ "$(t_where "$TARGET")" != "-" ] \
         && [ -x "$(t_where "$TARGET")/bin/splunk" ]; then
        home="$(t_where "$TARGET")"
    else
        home="$(sh_t 'printenv SPLUNK_HOME 2>/dev/null' 2>/dev/null | trim)"
        if [ -z "$home" ]; then
            local bin
            bin="$(sh_t 'command -v splunk 2>/dev/null' 2>/dev/null | trim)"
            [ -n "$bin" ] && home="$(sh_t "readlink -f '$bin' 2>/dev/null | sed 's|/bin/splunk$||'" 2>/dev/null | trim)"
        fi
        if [ -z "$home" ]; then
            home="$(sh_t 'find / -maxdepth 3 -type f -path "*/bin/splunk" 2>/dev/null | head -1 | sed "s|/bin/splunk$||"' 2>/dev/null | trim)"
        fi
    fi
    emit SPLUNK_HOME "$home"
    if [ -z "$home" ] || ! sh_t "test -x '$home/bin/splunk'" >/dev/null 2>&1; then
        emit ERROR "no splunk installation found"
        finding "no Splunk installation at $TARGET" \
                "pass --home <SPLUNK_HOME> if it is somewhere unusual"
        return
    fi

    # The account splunkd runs as, before any CLI call. var/ is
    # authoritative: splunkd must write its pid file there, and the CLI
    # chowns SPLUNK_HOME to whoever invokes it.
    emit SERVICE_USER  "$(sh_t "stat -c '%U' '$home/var' 2>/dev/null" 2>/dev/null | trim)"
    emit SERVICE_GROUP "$(sh_t "stat -c '%G' '$home/var' 2>/dev/null" 2>/dev/null | trim)"
    case "$(t_kind "$TARGET")" in
        podman|docker)
            emit CONTAINER_USER "$(t_runtime "$TARGET" >/dev/null; "$(t_runtime "$TARGET")" inspect "$(t_where "$TARGET")" --format '{{.Config.User}}' 2>/dev/null)" ;;
    esac

    # Version and product from the shipped manifest: a file read writes
    # nothing. PRODUCT reads "splunk" on a forwarder too, so role comes from
    # the file layout instead.
    local vf
    vf="$(sh_t "cat '$home/etc/splunk.version' 2>/dev/null" 2>/dev/null | trim)"
    emit VERSION  "$(printf '%s\n' "$vf" | sed -nE 's/^VERSION=//p' | head -1)"
    emit BUILD    "$(printf '%s\n' "$vf" | sed -nE 's/^BUILD=//p' | head -1)"
    emit PRODUCT  "$(printf '%s\n' "$vf" | sed -nE 's/^PRODUCT=//p' | head -1)"
    emit PLATFORM "$(printf '%s\n' "$vf" | sed -nE 's/^PLATFORM=//p' | head -1)"
    emit ROLE ""
    if sh_t "test -d '$home/share/splunk/search_mrsparkle'" >/dev/null 2>&1; then
        emit ROLE full
    elif sh_t "test -d '$home/etc/apps/SplunkUniversalForwarder'" >/dev/null 2>&1; then
        emit ROLE forwarder
    fi

    # Liveness from the pid file, so no CLI call is needed to answer it.
    emit RUNNING 0
    if sh_t "p=\$(head -1 '$home/var/run/splunk/splunkd.pid' 2>/dev/null); test -n \"\$p\" && test -d /proc/\$p" >/dev/null 2>&1; then
        emit RUNNING 1
    else
        finding "splunkd is not running at $TARGET" \
                "start it as $([ -n "${F[SERVICE_USER]:-}" ] && echo "${F[SERVICE_USER]}" || echo 'its service account'), and check var/log/splunk/crash-*.log if it does not stay up"
    fi

    local apps
    apps="$(sh_t "ls -1 '$home/etc/apps' 2>/dev/null" 2>/dev/null | trim | tr '\n' ',' | sed 's/,$//')"
    emit APPS "$apps"
    emit APP_COUNT "$(printf '%s' "$apps" | tr ',' '\n' | grep -c . || true)"
    for probe in Splunk_TA_nix Splunk_TA_windows Splunk_SA_CIM splunk_httpinput; do
        local present=0
        printf '%s' "$apps" | tr ',' '\n' | grep -qx "$probe" && present=1
        emit "HAS_${probe}" "$present"
    done

    emit INDEXES "$(sh_svc "'$home/bin/splunk' btool indexes list 2>/dev/null | sed -n 's/^\[\(.*\)\]$/\1/p' | sort | tr '\n' ',' | sed 's/,\$//'" 2>/dev/null | trim)"
    emit OUTPUT_SERVERS "$(sh_svc "'$home/bin/splunk' btool outputs list 2>/dev/null | sed -nE 's/^server[[:space:]]*=[[:space:]]*//p' | tr '\n' ',' | sed 's/,\$//'" 2>/dev/null | trim)"
    emit BTOOL_CHECK_LINES "$(sh_svc "'$home/bin/splunk' btool check 2>&1 | grep -c . || true" 2>/dev/null | trim)"
    emit CRASH_LOGS "$(sh_t "ls '$home/var/log/splunk/'crash-*.log 2>/dev/null | wc -l" 2>/dev/null | trim)"
    if [ "${F[CRASH_LOGS]:-0}" -gt 0 ] 2>/dev/null; then
        finding "${F[CRASH_LOGS]} crash log(s) in $home/var/log/splunk" \
                "read the newest for the faulting thread before assuming a configuration fault"
    fi

    emit IS_CONTAINER 0
    case "$(t_kind "$TARGET")" in podman|docker|k8s) emit IS_CONTAINER 1 ;; esac
    emit CONFIG_PERSISTS "$(t_can_persist "$TARGET" && echo 1 || echo 0)"
    if ! t_can_persist "$TARGET"; then
        finding "configuration written here does not survive replacement" \
                "$(t_persist_advice "$TARGET")"
    fi
}

# ---------------------------------------------------- what can it receive

discover_inputs() {
    local home="${F[SPLUNK_HOME]:-}"
    [ -n "$home" ] || return 0
    local bt
    bt="$(sh_svc "'$home/bin/splunk' btool inputs list 2>/dev/null")" || true
    [ -n "$bt" ] || { finding "could not read the inputs configuration" \
                      "check that btool runs as ${F[SERVICE_USER]:-the service account}"; return 0; }

    local idx_list=",${F[INDEXES]:-},"

    # A stanza's index and source type decide whether data lands where it is
    # expected. Missing either is silent, so both are reported per stanza.
    local stanzas
    stanzas="$(printf '%s\n' "$bt" | sed -n 's/^\[\(.*\)\]$/\1/p')"

    # HEC.
    local hec_disabled hec_port hec_ssl tok_count
    hec_disabled="$(printf '%s\n' "$bt" | awk '/^\[http\]$/{f=1;next} /^\[/{f=0} f && /^disabled/{print $3; exit}')"
    hec_port="$(printf '%s\n' "$bt" | awk '/^\[http\]$/{f=1;next} /^\[/{f=0} f && /^port/{print $3; exit}')"
    hec_ssl="$(printf '%s\n' "$bt" | awk '/^\[http\]$/{f=1;next} /^\[/{f=0} f && /^enableSSL/{print $3; exit}')"
    tok_count="$(printf '%s\n' "$stanzas" | grep -c '^http://' || true)"
    emit HEC_ENABLED "$([ "${hec_disabled:-1}" = "0" ] && echo 1 || echo 0)"
    emit HEC_PORT "${hec_port:-}"
    emit HEC_SSL "${hec_ssl:-}"
    emit HEC_TOKENS "${tok_count:-0}"
    if [ "${F[HEC_ENABLED]}" = "1" ] && [ "${tok_count:-0}" -eq 0 ]; then
        finding "HEC is enabled but no token is defined" \
                "add an [http://<name>] stanza with token and index, or events are rejected"
    fi
    if [ "${F[HEC_ENABLED]}" = "0" ] && [ "${F[HAS_splunk_httpinput]:-0}" = "1" ]; then
        finding "HEC is disabled" \
                "set disabled = 0 in the [http] stanza of splunk_httpinput/local/inputs.conf, the app that owns it, then restart splunkd"
    fi

    # Receiving from forwarders, raw TCP, and UDP.
    emit S2S_PORTS "$(printf '%s\n' "$stanzas" | sed -nE 's#^splunktcp(-ssl)?://(.*)$#\2#p' | tr '\n' ',' | sed 's/,$//')"
    emit TCP_PORTS "$(printf '%s\n' "$stanzas" | sed -nE 's#^tcp://(.*)$#\1#p' | tr '\n' ',' | sed 's/,$//')"
    emit UDP_PORTS "$(printf '%s\n' "$stanzas" | sed -nE 's#^udp://(.*)$#\1#p' | tr '\n' ',' | sed 's/,$//')"
    emit MONITOR_COUNT "$(printf '%s\n' "$stanzas" | grep -c '^monitor://' || true)"
    emit SCRIPT_COUNT "$(printf '%s\n' "$stanzas" | grep -c '^script://' || true)"

    if [ "${F[ROLE]:-}" = "full" ] && [ -z "${F[S2S_PORTS]}" ]; then
        finding "this instance is not receiving from forwarders" \
                "run: splunk enable listen 9997, or add a [splunktcp://9997] stanza, if forwarders should send here"
    fi

    # Per-stanza settings for every receiving path, including whether the
    # index it names actually exists.
    local details=""
    local st key idx sty mes dis
    while IFS= read -r st; do
        case "$st" in
            tcp://*|udp://*|splunktcp://*|splunktcp-ssl://*|http://*|monitor://*) ;;
            *) continue ;;
        esac
        key="$(printf '%s' "$st" | sed 's/[^A-Za-z0-9]/_/g')"
        idx="$(printf '%s\n' "$bt" | awk -v s="[$st]" '$0==s{f=1;next} /^\[/{f=0} f && /^index /{print $3; exit}')"
        sty="$(printf '%s\n' "$bt" | awk -v s="[$st]" '$0==s{f=1;next} /^\[/{f=0} f && /^sourcetype /{print $3; exit}')"
        dis="$(printf '%s\n' "$bt" | awk -v s="[$st]" '$0==s{f=1;next} /^\[/{f=0} f && /^disabled /{print $3; exit}')"
        mes="$(printf '%s\n' "$bt" | awk -v s="[$st]" '$0==s{f=1;next} /^\[/{f=0} f && /^maxEventSize /{print $3; exit}')"
        [ "${dis:-0}" = "1" ] && continue
        details="${details}${st} index=${idx:-<default>} sourcetype=${sty:-<autodetected>}"
        [ -n "$mes" ] && details="${details} maxEventSize=${mes}"
        details="${details}"$'\n'
        # A forwarder has no indexes.conf of its own, so its stanzas name
        # indexes that have to exist on the indexer at the end of the path.
        # Checking them against the forwarder would always pass. --trace
        # re-checks these against the terminal hop.
        if [ -n "$idx" ] && [ "${idx_list}" != ",," ] \
           && ! printf '%s' "$idx_list" | grep -q ",${idx},"; then
            finding "$st writes to index '$idx', which does not exist here" \
                    "create the index, or point the stanza at one that exists; events for a missing index are dropped"
        fi
        # An all-capitals token in a path is almost always a variable the
        # deployment was meant to substitute and did not, so the input
        # watches a directory that will never exist.
        case "$st" in
            monitor://*)
                if printf '%s' "$st" | grep -qE '/[A-Z][A-Z0-9_]{3,}(/|$)'; then
                    finding "$st contains what looks like an unexpanded placeholder" \
                            "the deployment did not substitute it, so nothing is collected from that path; render the value or remove the stanza"
                fi ;;
        esac
        case "$st" in
            tcp://*|udp://*)
                if [ -z "$sty" ]; then
                    finding "$st sets no sourcetype" \
                            "set sourcetype on the stanza: a raw stream carries no metadata, so Splunk guesses and parsing may not match"
                fi ;;
        esac
        case "$st" in
            udp://*)
                if [ -z "$mes" ]; then
                    finding "$st does not set maxEventSize" \
                            "the default is 1024 bytes and a larger datagram is truncated on arrival; XML event sources exceed it"
                fi ;;
        esac
    done <<< "$stanzas"
    emit RECEIVERS "$(printf '%s' "$details" | grep -c . || true)"
    emit RECEIVER_DETAIL "$(printf '%s' "$details" | tr '\n' ';' | sed 's/;$//')"

    # A forwarder with nowhere to send is a complete break in the chain.
    if [ "${F[ROLE]:-}" = "forwarder" ] && [ -z "${F[OUTPUT_SERVERS]:-}" ]; then
        finding "this forwarder has no output server configured" \
                "add a [tcpout:<group>] stanza with server = <indexer>:9997, or nothing it collects leaves the host"
    fi
}

# ----------------------------------------------------------- log discovery

discover_logs() {
    emit LOGS_TRANSPORT "$(t_kind "$LOGS_AT")"
    emit LOGS_LOCATION  "$(t_where "$LOGS_AT")"
    if [ -z "$SOURCES" ]; then
        emit ERROR "--logs needs --sources; the operator declares which paths are in scope"
        return
    fi
    local found=() missing=() unreadable=()
    local IFS_SAVE="$IFS"; IFS=','
    for entry in $SOURCES; do
        IFS="$IFS_SAVE"
        local path="${entry%%:*}"
        if sh_logs "test -e '$path'" >/dev/null 2>&1; then
            if sh_logs "test -r '$path'" >/dev/null 2>&1; then
                found+=("${path}:$(sh_logs "stat -c%s '$path' 2>/dev/null" 2>/dev/null | trim)")
            else
                unreadable+=("$path")
                finding "$path exists but is not readable" \
                        "the collecting account needs read access, commonly via the adm or root group"
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

    emit AUDITD_PRESENT 0
    sh_logs 'command -v auditctl >/dev/null 2>&1' >/dev/null 2>&1 && emit AUDITD_PRESENT 1
    emit AUDITD_ACTIVE 0
    sh_logs 'systemctl is-active auditd 2>/dev/null | grep -qx active' >/dev/null 2>&1 && emit AUDITD_ACTIVE 1

    local al=""
    for entry in $(printf '%s' "$SOURCES" | tr ',' ' '); do
        case "$entry" in */audit.log*) al="${entry%%:*}" ;; esac
    done
    if [ -n "$al" ] && sh_logs "test -r '$al'" >/dev/null 2>&1; then
        emit AUDIT_EXECVE_RECORDS "$(sh_logs "grep -c '^type=EXECVE' '$al' 2>/dev/null || true" 2>/dev/null | trim)"
        emit AUDIT_TOTAL_RECORDS  "$(sh_logs "grep -c '^type=' '$al' 2>/dev/null || true" 2>/dev/null | trim)"
        if [ "${F[AUDIT_EXECVE_RECORDS]:-0}" -lt 10 ] 2>/dev/null; then
            finding "the audit log holds ${F[AUDIT_EXECVE_RECORDS]:-0} EXECVE record(s)" \
                    "most auditd detection content matches execve; add an audit rule such as -a always,exit -F arch=b64 -S execve -k exec, or those rules cannot fire"
        fi
    fi
}

# ------------------------------------------------------- topology tracing

# Follow outputs.conf from one hop to the next, so a path such as
# UF -> HF -> indexer is reported as a chain rather than as three unrelated
# instances. Data can stop at any hop, and which hop decides where to look.
#
# A hostname in outputs.conf is not a transport target, and nothing on the
# instance says how to reach it, so the operator declares the mapping:
#
#   --map 'hf01=ssh:splunk@hf01,idx01=podman:idx01'
#
# Matching is on the host part of server=, ignoring the port.
resolve_hop() {
    local host="$1" entry
    for entry in $(printf '%s' "$HOP_MAP" | tr ',' ' '); do
        case "$entry" in
            "${host}="*) printf '%s' "${entry#*=}"; return 0 ;;
        esac
    done
    return 1
}

discover_trace() {
    local hop=1 cur="$TARGET" chain="" seen=""
    local home role outs first_server host nexthop iandf

    while [ -n "$cur" ] && [ "$hop" -le 6 ]; do
        case ",$seen," in
            *",$cur,"*) finding "the forwarding path loops back to $cur" \
                                "a cycle in outputs.conf sends data in circles; correct one hop's server setting"
                        break ;;
        esac
        seen="${seen},${cur}"

        home="$(t_sh "$cur" 'printenv SPLUNK_HOME 2>/dev/null' 2>/dev/null | trim)"
        [ -z "$home" ] && home="/opt/splunk"
        if ! t_sh "$cur" "test -x '$home/bin/splunk'" >/dev/null 2>&1; then
            for cand in /opt/splunk /opt/splunkforwarder; do
                t_sh "$cur" "test -x '$cand/bin/splunk'" >/dev/null 2>&1 && home="$cand" && break
            done
        fi
        local svc
        svc="$(t_sh "$cur" "stat -c '%U' '$home/var' 2>/dev/null" 2>/dev/null | trim)"
        role="full"
        t_sh "$cur" "test -d '$home/etc/apps/SplunkUniversalForwarder'" >/dev/null 2>&1 \
            && ! t_sh "$cur" "test -d '$home/share/splunk/search_mrsparkle'" >/dev/null 2>&1 \
            && role="forwarder"

        outs="$(t_sh_as "$cur" "$svc" "'$home/bin/splunk' btool outputs list 2>/dev/null")" || true
        first_server="$(printf '%s\n' "$outs" | sed -nE 's/^server[[:space:]]*=[[:space:]]*//p' | head -1 | cut -d, -f1 | trim)"

        # A forwarding tier that also indexes, or that is told to index
        # instead of forwarding, is a common place for data to vanish.
        iandf="$(printf '%s\n' "$outs" | sed -nE 's/^indexAndForward[[:space:]]*=[[:space:]]*//p' | head -1 | trim)"

        if [ -z "$first_server" ]; then
            chain="${chain}${hop}. ${cur} [${role}] terminal, indexes locally"$'\n'
            if [ "$role" = "forwarder" ]; then
                finding "hop ${hop} ${cur} is a forwarder with no output server" \
                        "data stops here; add a [tcpout:<group>] stanza with server = <next hop>:9997"
            fi
            break
        fi

        chain="${chain}${hop}. ${cur} [${role}] -> ${first_server}"
        [ -n "$iandf" ] && chain="${chain} indexAndForward=${iandf}"
        chain="${chain}"$'\n'

        if [ "$iandf" = "true" ] || [ "$iandf" = "1" ]; then
            finding "hop ${hop} ${cur} has indexAndForward enabled" \
                    "it indexes a copy locally as well as forwarding; confirm that is intended, and that the local index exists, or events are written somewhere nobody searches"
        fi

        host="${first_server%%:*}"
        if nexthop="$(resolve_hop "$host")"; then
            cur="$nexthop"
            hop=$((hop+1))
        else
            chain="${chain}${hop}. next hop ${host} is not mapped"$'\n'
            finding "the path continues to ${host}, which is not reachable from here" \
                    "add it to --map, for example --map '${host}=ssh:splunk@${host}', to trace the rest of the chain"
            break
        fi
    done

    emit PATH_HOPS "$(printf '%s' "$chain" | grep -c . || true)"
    emit PATH_CHAIN "$(printf '%s' "$chain" | tr '\n' ';' | sed 's/;$//')"

    # The indexes this instance's inputs name have to exist at the end of
    # the path, not here. Now that the terminal hop is known, re-check them
    # there: an input on a forwarder pointing at an index the indexer does
    # not have is a silent drop, and it cannot be detected from the
    # forwarder alone.
    local terminal="$cur"
    [ "$terminal" = "$TARGET" ] && return 0
    local thome tsvc tindexes
    thome="$(t_sh "$terminal" 'printenv SPLUNK_HOME 2>/dev/null' 2>/dev/null | trim)"
    [ -z "$thome" ] && thome="/opt/splunk"
    tsvc="$(t_sh "$terminal" "stat -c '%U' '$thome/var' 2>/dev/null" 2>/dev/null | trim)"
    tindexes="$(t_sh_as "$terminal" "$tsvc" "'$thome/bin/splunk' btool indexes list 2>/dev/null | sed -n 's/^\[\(.*\)\]\$/\1/p' | sort | tr '\n' ',' | sed 's/,\$//'" 2>/dev/null | trim)"
    [ -z "$tindexes" ] && return 0
    emit TERMINAL_HOP "$terminal"
    emit TERMINAL_INDEXES "$tindexes"

    local checked="" named
    while IFS= read -r line; do
        named="$(printf '%s' "$line" | sed -nE 's/.* index=([^ ]+).*/\1/p')"
        [ -z "$named" ] && continue
        case "$named" in '<default>'|_*) continue ;; esac
        case ",$checked," in *",$named,"*) continue ;; esac
        checked="${checked},${named}"
        if ! printf ',%s,' "$tindexes" | grep -q ",${named},"; then
            finding "an input here writes to index '$named', absent on the terminal indexer $terminal" \
                    "create '$named' on $terminal, or repoint the input; the forwarder accepts it and the indexer discards it"
        fi
    done <<< "$(printf '%s' "${F[RECEIVER_DETAIL]:-}" | tr ';' '\n')"
}

[ -n "$TARGET" ]  && discover_target
[ -n "$TARGET" ] && [ "$WANT_INPUTS" = "1" ] && [ -z "${F[ERROR]:-}" ] && discover_inputs
[ -n "$TARGET" ] && [ "$WANT_TRACE" = "1" ] && [ -z "${F[ERROR]:-}" ] && discover_trace
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
    if [ ${#FINDINGS[@]} -gt 0 ]; then
        printf ',\n  "findings": [\n'
        for i in "${!FINDINGS[@]}"; do
            [ "$i" -gt 0 ] && printf ',\n'
            printf '    {"issue": "%s", "action": "%s"}' \
                "$(printf '%s' "${FINDINGS[$i]%%|*}" | sed 's/"/\\"/g')" \
                "$(printf '%s' "${FINDINGS[$i]#*|}" | sed 's/"/\\"/g')"
        done
        printf '\n  ]'
    fi
    printf '\n}\n'
else
    echo "# Discovered $(date -u +%Y-%m-%dT%H:%M:%SZ). Facts only; empty means not established."
    for k in $(printf '%s\n' "${!F[@]}" | sort); do
        printf '%s%s=%s\n' "$P" "$k" "$(printf '%q' "${F[$k]}")"
    done
    # The chain is for a person to read, so it is printed unquoted as well
    # as being available shell-escaped above.
    if [ -n "${F[PATH_CHAIN]:-}" ]; then
        echo
        echo "# Forwarding path, ${F[PATH_HOPS]:-0} hop(s). Data can stop at any of them."
        printf '%s' "${F[PATH_CHAIN]}" | tr ';' '\n' | sed 's/^/#   /'
    fi
    if [ -n "${F[RECEIVER_DETAIL]:-}" ]; then
        echo
        echo "# Enabled receivers, with what decides where their data lands."
        printf '%s' "${F[RECEIVER_DETAIL]}" | tr ';' '\n' | sed 's/^/#   /'
    fi
    if [ ${#FINDINGS[@]} -gt 0 ]; then
        echo
        echo "# ${#FINDINGS[@]} finding(s). Each needs an operator action before data will flow as expected."
        for entry in "${FINDINGS[@]}"; do
            printf '#\n#  %s\n#      fix: %s\n' "${entry%%|*}" "${entry#*|}"
        done
    fi
fi

[ -n "${F[ERROR]:-}" ] && exit 1
exit 0
