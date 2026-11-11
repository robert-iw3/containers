#!/usr/bin/env bash
# Empty an index, keeping its definition.
#
# 'splunk clean eventdata' deletes the buckets and reclaims the disk, which
# is what emptying should mean. It is not the same as a search-time delete,
# which only marks events unsearchable and reclaims nothing.
#
# It needs splunkd stopped, so this is an outage for the whole instance, not
# just for the index named.
#
#   ./bin/index-empty.sh --container splunk --index lab --dry-run
#   ./bin/index-empty.sh --container splunk --index lab --index lab2 --yes
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,13p' "$0"; exit "${1:-0}"; }
IDX=()
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --index)   IDX+=("${2:-}"); shift 2 ;;
        -h|--help) usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
[ "${#IDX[@]}" -gt 0 ] || usage 2
im_resolve_user

im_head "What would be deleted"
for i in "${IDX[@]}"; do
    im_index_exists "$i" || im_die "the index '$i' does not exist"
    h="$(im_index_path "$i")"; b="${h%/db}"
    k="$(im_num "$(im_run "du -sk '$b' 2>/dev/null | cut -f1" | tr -d '\r')")"
    n="$(im_num "$(im_run "ls -d '$b'/db/db_* '$b'/db/hot_* '$b'/colddb/db_* 2>/dev/null | wc -l" | tr -d '\r')")"
    printf '  %-26s %s bucket(s)  %s MB\n' "$i" "$n" "$(( k / 1024 ))"
done

[ "$IM_DRY" = "1" ] && { echo; im_say "dry run; nothing was deleted"; echo; exit 0; }

im_confirm "Permanently delete the data in: ${IDX[*]}. This cannot be undone, and splunkd will be stopped for the whole instance."

STARTED=0
if im_splunkd_running; then im_stop; STARTED=1; fi
im_head "Emptying"
for i in "${IDX[@]}"; do
    im_say "$i"
    im_run "$IM_SPLUNK_HOME/bin/splunk clean eventdata -index '$i' -f" 2>&1 \
        | grep -v 'Server Certificate' | sed 's/^/      /'
done
[ "$STARTED" = "1" ] && im_start

im_head "Result"
for i in "${IDX[@]}"; do
    h="$(im_index_path "$i")"; b="${h%/db}"
    k="$(im_num "$(im_run "du -sk '$b' 2>/dev/null | cut -f1" | tr -d '\r')")"
    printf '  %-26s %s KB\n' "$i" "$k"
done
echo
im_say "Only the enabled inputs will repopulate these."
echo
