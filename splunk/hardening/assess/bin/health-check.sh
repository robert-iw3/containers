#!/usr/bin/env bash
# Splunk instance health: the gate every hardening change is measured against.
#
# WHY THIS EXISTS. A hardening change can only be attributed to a change if the
# instance was known-good beforehand. This captures that state as VALUES, not as
# pass or fail, because health is a comparison: three forwarder connections
# before a change and two after is a regression even though two exceeds zero.
#
# AUTH-FREE ON PURPOSE. `splunk btool` and `splunk status` need no credentials and
# no cached session, and btool works with splunkd stopped. The REST path through
# `splunk _internal call` needs a session token that is per-user, per-host and
# per-port, so it is absent on a forwarder nobody has logged into - measured. A
# health check that cannot run on a forwarder is not a health check, so nothing
# here depends on authentication.
#
#   health-check.sh                       report, compare against the stored baseline
#   health-check.sh --baseline            write the baseline and report
#   health-check.sh (containers: use bin/in-container.sh)
#   health-check.sh --out DIR             where baseline and reports are kept
#   health-check.sh --log-lines N         how many trailing splunkd.log lines to count
#
# EXIT CONTRACT, four values. "Could not determine" is not a pass.
#   0 healthy      every probe answered, nothing regressed against the baseline
#   1 degraded     a probe answered and the answer is bad, or regressed
#   2 undetermined a probe could not answer; the state is unknown, not good
#   3 error        this script could not run
set -uo pipefail

MODE="report"; OUT=""; LOG_LINES=5000
SPLUNK_HOME_OVERRIDE=""

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

# Splunk discovery and the privilege guard are shared: the guard is safety-critical
# and a guard copied into five scripts is one that drifts. Sourced BEFORE the option
# loop so its defaults are set and the options then override them.
# The shared library sits at ../lib when this module is staged flat (as
# in-container.sh stages it) and at ../../lib in the repository layout. Search
# rather than assume: a wrong guess fails at the first line of every run.
LIB=""
for _c in "$(dirname "$0")/../lib" "$(dirname "$0")/../../lib" "$(dirname "$0")"; do
    [ -r "${_c}/lib-target.sh" ] && { LIB="$(cd "$_c" && pwd)/lib-target.sh"; break; }
done
[ -n "$LIB" ] || { printf 'cannot find lib-target.sh near %s\n' "$(dirname "$0")" >&2; exit 3; }
. "$LIB"

# Kept verbatim so the privilege guard can print the command to re-run.
TGT_ORIGINAL_ARGS="$*"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --baseline)    MODE="baseline"; shift ;;
        --out)         OUT="${2:-}"; shift 2 ;;
        --log-lines)   LOG_LINES="${2:-5000}"; shift 2 ;;
        --splunk-home) SPLUNK_HOME_OVERRIDE="${2:-}"; shift 2 ;;
        --allow-wrong-user) TGT_ALLOW_WRONG_USER=1; shift ;;
        -h|--help)     usage 0 ;;
        *) printf 'unknown argument: %s\n' "$1" >&2; usage 3 ;;
    esac
done

if [ -t 1 ]; then G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; Z=$'\033[0m'
else G=""; R=""; Y=""; B=""; Z=""; fi

HEALTHY=0; DEGRADED=0; UNDET=0
declare -a VALUES=()

ok()    { printf '  %s[ OK ]%s %-34s %s\n' "$G" "$Z" "$1" "${2:-}"; HEALTHY=$((HEALTHY+1)); }
bad()   { printf '  %s[BAD ]%s %-34s %s\n' "$R" "$Z" "$1" "${2:-}"; DEGRADED=$((DEGRADED+1)); }
unk()   { printf '  %s[ ?? ]%s %-34s %s\n' "$Y" "$Z" "$1" "${2:-}"; UNDET=$((UNDET+1)); }
info()  { printf '        %-34s %s\n' "$1" "${2:-}"; }
say()   { printf '\n%s== %s%s\n' "$B" "$1" "$Z"; }

# Record a measured value for the baseline. Values are compared, not thresholded.
val() { VALUES+=("$1	$2"); }

# Numbers from command output are not trusted to be numbers. An unquoted compare
# against "None" aborts the script under set -u rather than reading false.
num() { case "${1:-}" in ''|*[!0-9]*) printf '0' ;; *) printf '%s' "$1" ;; esac; }

# ---------------------------------------------------------------- target access




TGT_SPLUNK_HOME_HINT="$SPLUNK_HOME_OVERRIDE"
target_init || exit 3

[ -n "$OUT" ] || OUT="$(cd "$(dirname "$0")/.." && pwd)/out"
mkdir -p "$OUT" 2>/dev/null || { printf 'cannot write to %s\n' "$OUT" >&2; exit 3; }
# The Splunk image ships without `hostname`, the same way it ships without curl,
# so the name is read from the places that do not need a binary.
LABEL="$(hostname 2>/dev/null)"
[ -n "$LABEL" ] || LABEL="${HOSTNAME:-}"
[ -n "$LABEL" ] || LABEL="$(cat /etc/hostname 2>/dev/null | sed -n 1p)"
[ -n "$LABEL" ] || LABEL="local"
LABEL="$(printf '%s' "$LABEL" | tr -c 'A-Za-z0-9._-' '_')"
BASE="${OUT}/baseline-${LABEL}.tsv"

printf '%s== Splunk health: %s%s\n' "$B" "$LABEL" "$Z"
info "SPLUNK_HOME" "$SPLUNK_HOME"

# ---------------------------------------------------------------- 1. liveness
say "Liveness"
status_out="$(sp status)"
if [ -z "$status_out" ]; then
    unk "splunkd status" "the CLI produced no output"
    val splunkd_running unknown
elif [ "$(printf '%s' "$status_out" | grep -c 'splunkd is running')" -gt 0 ]; then
    pid="$(printf '%s' "$status_out" | sed -n 's/.*PID: \([0-9]*\).*/\1/p' | sed -n 1p)"
    ok "splunkd running" "pid ${pid:-unknown}"
    val splunkd_running yes
else
    bad "splunkd not running" "$(printf '%s' "$status_out" | sed -n 1p)"
    val splunkd_running no
fi

# A forwarder prints an ownership warning before the version line, so match the
# line that actually carries a version rather than the first line.
ver="$(sp version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' | sed -n 1p)"
if [ -n "$ver" ]; then ok "version" "$ver"; val version "$ver"
else unk "version" "could not read"; val version unknown; fi

# ---------------------------------------------------------- 2. config integrity
say "Configuration integrity"
# btool check EXITS 0 EVEN WHEN IT REPORTS ERRORS. The output is the result; the
# status is not. This was measured, and it is why the count is parsed.
bt_out="$(sp btool check)"
if [ -z "$bt_out" ]; then
    ok "btool check" "no findings"
    val btool_invalid_keys 0; val btool_total_findings 0
else
    inv="$(num "$(printf '%s' "$bt_out" | grep -c 'Invalid key')")"
    tot="$(num "$(printf '%s' "$bt_out" | grep -c .)")"
    val btool_invalid_keys "$inv"; val btool_total_findings "$tot"
    if [ "$inv" -gt 0 ]; then
        bad "btool check: invalid keys" "$inv (a key the product does not read)"
        printf '%s' "$bt_out" | grep 'Invalid key' | sed -n '1,3p' | sed 's/^[[:space:]]*/         /'
        [ "$inv" -gt 3 ] && info "" "... and $((inv-3)) more"
    else
        ok "btool check: no invalid keys" "$tot other line(s)"
    fi
fi

# ------------------------------------------------------------ 3. role discovery
# The functional checks are role-derived, so the role is read from configuration
# rather than assumed. Read-only and auth-free.
say "Role"
ROLE_IDX=0; ROLE_FWD=0; ROLE_SH=0; ROLE_FWD_IN=0
# Only stanzas the site configured count toward a role. btool reports the file each
# setting came from, so a stanza whose source is system/default is a shipped default
# and says nothing about what this instance is for. Counting those classified a heavy
# forwarder as an indexer and then failed it for not indexing - measured.
cfg() { grep -v '/etc/system/default/'; }
recv="$(num "$(sp btool inputs list --debug | cfg | grep -cE '\[splunktcp')")"
[ "$recv" -gt 0 ] && ROLE_FWD_IN=1
tcpout="$(num "$(sp btool outputs list --debug | cfg | grep -cE '\[tcpout')")"
[ "$tcpout" -gt 0 ] && ROLE_FWD=1
peers="$(num "$(sp btool distsearch list --debug | cfg | grep -cE 'servers *=')")"
[ "$peers" -gt 0 ] && ROLE_SH=1
idxcount="$(num "$(sp btool indexes list --debug | cfg | grep -cE '\[[a-zA-Z]')")"
# An indexing role is one with indexes of its own, not one that merely listens.
[ "$idxcount" -gt 0 ] && ROLE_IDX=1

roles=""
[ "$ROLE_IDX" -eq 1 ]    && roles="${roles}indexer "
[ "$ROLE_FWD_IN" -eq 1 ] && roles="${roles}receiver "
[ "$ROLE_FWD" -eq 1 ]    && roles="${roles}forwarder "
[ "$ROLE_SH" -eq 1 ]     && roles="${roles}search-head "
[ -n "$roles" ] || roles="standalone "
ok "role" "${roles% }"
val role "$(printf '%s' "${roles% }" | tr ' ' ',')"
val receiving_stanzas "$recv"; val tcpout_groups "$tcpout"; val index_stanzas "$idxcount"
info "configured receiving stanzas" "$recv"
info "tcpout groups" "$tcpout"
info "configured index stanzas" "$idxcount"

# ------------------------------------------------------------ 4. data movement
# metrics.log is the oracle that separates two failures a search cannot tell
# apart: events that never reached the index writer, and events indexed but
# invisible to the searching role.
say "Data movement"
MET="${SPLUNK_HOME}/var/log/splunk/metrics.log"
if [ -z "$(sh_in "[ -r '$MET' ] && echo y")" ]; then
    unk "metrics.log" "not readable at ${MET}"
    val index_thruput_ev unknown; val thruput_kbps unknown; val blocked_queues unknown
else
    # Last reported value, not an average: sed -n '$p' on the matching lines.
    ev="$(sh_in "grep 'name=index_thruput' '$MET' | tail -40 | sed -n '\$p'" | sed -n 's/.*[ ,]ev=\([0-9]*\).*/\1/p')"
    kb="$(sh_in "grep 'group=thruput, name=thruput' '$MET' | tail -40 | sed -n '\$p'" | sed -n 's/.*[ ,]kbps=\([0-9.]*\).*/\1/p')"
    blk="$(num "$(sh_in "tail -2000 '$MET' | grep -c 'blocked=true'")")"
    if [ -n "$ev" ]; then
        val index_thruput_ev "$ev"
        if [ "$ROLE_IDX" -eq 1 ] || [ "$idxcount" -gt 0 ]; then
            if [ "$(num "$ev")" -gt 0 ]; then ok "events reaching the index writer" "ev=$ev"
            else bad "index_thruput ev=0" "events are not reaching the index writer; suspect routing"; fi
        else
            info "index_thruput" "ev=$ev (not an indexing role)"
        fi
    elif [ "$ROLE_IDX" -eq 1 ]; then
        unk "index_thruput" "no sample in metrics.log on an indexing role"
        val index_thruput_ev unknown
    else
        info "index_thruput" "no sample (not an indexing role)"
        val index_thruput_ev not_applicable
    fi
    [ -n "$kb" ] && { info "thruput" "${kb} kbps"; val thruput_kbps "$kb"; } || val thruput_kbps unknown
    val blocked_queues "$blk"
    if [ "$blk" -gt 0 ]; then bad "blocked queues" "$blk sample(s) report blocked=true"
    else ok "no blocked queues" "over the last 2000 samples"; fi
fi

# ------------------------------------------------------------------- 5. errors
say "Errors in the last ${LOG_LINES} log line(s)"
LOG="${SPLUNK_HOME}/var/log/splunk/splunkd.log"
if [ -z "$(sh_in "[ -r '$LOG' ] && echo y")" ]; then
    unk "splunkd.log" "not readable at ${LOG}"
    val log_errors unknown; val log_warns unknown
else
    # grep -c, never grep -q: under pipefail a quiet grep exits on first match and
    # the writer takes SIGPIPE 141, which inverts the sense of the test.
    errs="$(num "$(sh_in "tail -"$LOG_LINES" '$LOG' | grep -c ' ERROR '")")"
    warns="$(num "$(sh_in "tail -"$LOG_LINES" '$LOG' | grep -c ' WARN '")")"
    fatal="$(num "$(sh_in "tail -"$LOG_LINES" '$LOG' | grep -c ' FATAL '")")"
    val log_errors "$errs"; val log_warns "$warns"; val log_fatal "$fatal"
    if [ "$fatal" -gt 0 ]; then bad "FATAL in splunkd.log" "$fatal line(s)"
    elif [ "$errs" -gt 0 ]; then info "ERROR lines" "$errs (compared against the baseline)"; ok "no FATAL" ""
    else ok "no ERROR or FATAL" "over the last ${LOG_LINES} lines"; fi
    info "WARN lines" "$warns"
fi

# ------------------------------------------------------------------ 6. capacity
say "Capacity"
db="$(sp btool server list diskUsage --debug | sed -n 's/.*minFreeSpace *= *//p' | sed -n 1p)"
[ -n "$db" ] && { info "minFreeSpace" "$db"; val min_free_space "$db"; }
freemb="$(sh_in "df -Pm '${SPLUNK_HOME}' | sed -n '2p' | awk '{print \$4}'")"
freemb="$(num "$freemb")"
val free_mb "$freemb"
if [ "$freemb" -eq 0 ]; then unk "free space" "could not read"
elif [ -n "$db" ] && [ "$freemb" -lt "$(num "$db")" ]; then bad "free space below minFreeSpace" "${freemb}MB < ${db}MB"
else ok "free space" "${freemb}MB"; fi

# --------------------------------------------------------- baseline comparison
say "Baseline"
write_baseline() {
    { printf '# splunk health baseline\n# target\t%s\n# splunk_home\t%s\n' "$LABEL" "$SPLUNK_HOME"
      printf '%s\n' "${VALUES[@]}"; } > "$BASE"
    ok "baseline written" "$(basename "$BASE") (${#VALUES[@]} values)"
}

REGRESSED=0
if [ "$MODE" = "baseline" ]; then
    write_baseline
elif [ ! -f "$BASE" ]; then
    unk "no baseline to compare against" "run with --baseline once the instance is known-good"
else
    # Compare values, not thresholds. A count that fell is a regression even when
    # the absolute number still looks acceptable.
    while IFS="	" read -r k v; do
        case "$k" in ''|'#'*) continue ;; esac
        now=""
        for row in "${VALUES[@]}"; do
            case "$row" in "$k	"*) now="${row#*	}"; break ;; esac
        done
        [ -n "$now" ] || continue
        [ "$now" = "$v" ] && continue
        case "$k" in
            log_errors|log_warns|log_fatal|btool_invalid_keys|btool_total_findings|blocked_queues)
                if [ "$(num "$now")" -gt "$(num "$v")" ]; then
                    bad "increased: $k" "$v -> $now"; REGRESSED=$((REGRESSED+1))
                else info "decreased: $k" "$v -> $now"; fi ;;
            free_mb)
                # Recorded for context only. Free space moves on its own, so an exact
                # comparison reports noise; the absolute check against minFreeSpace
                # above is the one that means anything.
                info "free space moved" "$v -> $now" ;;
            index_thruput_ev|receiving_stanzas|tcpout_groups|index_stanzas)
                if [ "$(num "$now")" -lt "$(num "$v")" ]; then
                    bad "fell: $k" "$v -> $now"; REGRESSED=$((REGRESSED+1))
                else info "rose: $k" "$v -> $now"; fi ;;
            *)
                bad "changed: $k" "$v -> $now"; REGRESSED=$((REGRESSED+1)) ;;
        esac
    done < "$BASE"
    [ "$REGRESSED" -eq 0 ] && ok "no regression against the baseline" "$(basename "$BASE")"
fi

# ------------------------------------------------------------------- 7. verdict
REPORT="${OUT}/health-${LABEL}-$(date -u +%Y%m%dT%H%M%SZ).tsv"
{ printf '# splunk health report\n# target\t%s\n' "$LABEL"
  printf '%s\n' "${VALUES[@]}"; } > "$REPORT" 2>/dev/null || true

printf '\n%s== %s probe(s) good, %s bad, %s undetermined%s\n' "$B" "$HEALTHY" "$DEGRADED" "$UNDET" "$Z"
printf '   report: %s\n' "$REPORT"
if   [ "$DEGRADED" -gt 0 ] || [ "$REGRESSED" -gt 0 ]; then printf '   %sDEGRADED%s\n' "$R" "$Z"; exit 1
elif [ "$UNDET" -gt 0 ];    then printf '   %sUNDETERMINED - state is unknown, not good%s\n' "$Y" "$Z"; exit 2
else printf '   %sHEALTHY%s\n' "$G" "$Z"; exit 0; fi
