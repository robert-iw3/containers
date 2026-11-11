#!/usr/bin/env bash
# What indexes exist, how big they are, what they hold, and what is about to
# be deleted. Read-only: it changes nothing.
#
# Run this before any of the other scripts. Most index work goes wrong
# because of something visible here -- data older than the retention that
# is about to be frozen, a cap already reached, or an index that is not
# where its name suggests.
#
#   ./bin/index-inventory.sh --container splunk
#   ./bin/index-inventory.sh --splunk-home /opt/splunk --index main
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,12p' "$0"; exit "${1:-0}"; }
WANT=()
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --index) WANT+=("${2:-}"); shift 2 ;;
        -h|--help) usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
im_resolve_user

im_head "Installation"
im_say "SPLUNK_HOME  $IM_SPLUNK_HOME"
im_say "running as   $IM_USER${IM_CONTAINER:+  (in $IM_CONTAINER)}"
if im_splunkd_running; then im_say "splunkd      running"; else im_say "splunkd      stopped"; fi

# The names of every index btool knows, internal ones included: a full
# disk is a full disk whoever filled it.
ALL="$(im_run "$IM_SPLUNK_HOME/bin/splunk btool indexes list 2>/dev/null \
        | sed -n 's/^\[\(.*\)\]$/\1/p' | grep -v '^default$' | grep -v ':' | sort")"
[ "${#WANT[@]}" -gt 0 ] && [ -n "${WANT[0]:-}" ] && ALL="$(printf '%s\n' "${WANT[@]}")"

im_head "Indexes"
printf '  %-26s %9s %9s %10s %7s  %s\n' name size buckets retention cap state
printf '  %s\n' "$(printf '─%.0s' $(seq 1 92))"

TOTAL_KB=0
while read -r idx; do
    [ -n "$idx" ] || continue
    home="$(im_index_path "$idx")"
    base="${home%/db}"
    kb="$(im_num "$(im_run "du -sk '$base' 2>/dev/null | cut -f1" | tr -d '\r')")"
    TOTAL_KB=$(( TOTAL_KB + kb ))
    nb="$(im_num "$(im_run "ls -d '$base'/db/db_* '$base'/db/rb_* '$base'/colddb/db_* 2>/dev/null | wc -l" | tr -d '\r')")"
    nh="$(im_num "$(im_run "ls -d '$base'/db/hot_* 2>/dev/null | wc -l" | tr -d '\r')")"
    frozen="$(im_num "$(im_index_setting "$idx" frozenTimePeriodInSecs)")"
    cap="$(im_num "$(im_index_setting "$idx" maxTotalDataSizeMB)")"
    dis="$(im_index_setting "$idx" disabled)"
    state="enabled"
    [ "$dis" = "1" ] || [ "$dis" = "true" ] && state="DISABLED"
    [ "$nh" -gt 0 ] && state="$state, ${nh} hot"
    if [ "$frozen" -gt 0 ]; then ret="$(( frozen / 86400 ))d"; else ret="unset"; fi
    if   [ "$cap" -ge 1024 ]; then capd="$(( cap / 1024 ))G"
    elif [ "$cap" -gt 0 ];    then capd="${cap}M"
    else capd="unset"; fi
    pct=""
    if [ "$cap" -gt 0 ] && [ "$kb" -gt 0 ]; then
        pct=" $(( kb * 100 / (cap * 1024) ))%"
    fi
    printf '  %-26s %8sM %9s %10s %7s  %s\n' \
        "$idx" "$(( kb / 1024 ))" "$nb" "$ret" "$capd$pct" "$state"
done <<< "$ALL"
printf '  %s\n' "$(printf '─%.0s' $(seq 1 92))"
printf '  %-26s %8sM\n' "TOTAL" "$(( TOTAL_KB / 1024 ))"

# A bucket's directory name carries the newest and oldest event times it
# holds, so the span of an index can be read without a search.
im_head "What each index holds, from its bucket names"
while read -r idx; do
    [ -n "$idx" ] || continue
    home="$(im_index_path "$idx")"; base="${home%/db}"
    span="$(im_run "ls -d '$base'/db/db_* '$base'/colddb/db_* 2>/dev/null \
            | sed 's#.*/##' | awk -F_ '{print \$2\" \"\$3}'")"
    [ -n "$span" ] || { printf '  %-26s (no warm or cold buckets)\n' "$idx"; continue; }
    newest="$(printf '%s\n' "$span" | awk '{print $1}' | sort -n | tail -1)"
    oldest="$(printf '%s\n' "$span" | awk '{print $2}' | sort -n | sed -n 1p)"
    frozen="$(im_num "$(im_index_setting "$idx" frozenTimePeriodInSecs)")"
    note=""
    if [ "$frozen" -gt 0 ] && [ -n "$oldest" ]; then
        age=$(( ( $(date -u +%s) - oldest ) ))
        [ "$age" -gt "$frozen" ] && \
            note="  <-- older than its retention; this will be frozen"
    fi
    printf '  %-26s %s .. %s%s\n' "$idx" \
        "$(date -u -d "@$oldest" +'%F' 2>/dev/null || echo '?')" \
        "$(date -u -d "@$newest" +'%F' 2>/dev/null || echo '?')" "$note"
done <<< "$ALL"
echo
