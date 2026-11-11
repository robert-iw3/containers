#!/usr/bin/env bash
# Move a portion of an index into another index, chosen by search.
#
# This is the tool for "the firewall logs went to the wrong index" or "split
# this host out into its own index". It re-indexes the matching events into
# the destination, which is the only way to move *some* of an index: buckets
# are the unit on disk and a bucket holds whatever it holds.
#
# What re-indexing means, plainly:
#
#   _time is preserved, so searches over the destination see the original
#     event times.
#   _indextime becomes now. Anything keyed on index time -- and that
#     includes "how much did we ingest today" -- will show this.
#   it counts against the licence a second time. Moving 100 GB uses 100 GB
#     of the daily volume, so a large move wants to be split across days.
#   the originals are not removed. Nothing is destroyed by this script; see
#     --then-delete below for what removal does and does not do.
#
#   ./bin/index-move-events.sh --container splunk \
#       --from wrong_index --to right_index \
#       --where 'host=web-01' --earliest -7d --latest now
#
#   ./bin/index-move-events.sh --container splunk --from a --to b \
#       --where 'sourcetype=nginx:access' --earliest -30d@d --latest -0d@d --execute
#
# It counts first and refuses a move it cannot verify. Without --execute it
# reports what would move and stops.
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,29p' "$0"; exit "${1:-0}"; }
SRC=""; DST=""; WHERE=""; EARLY="-24h"; LATE="now"; EXEC=0; DELETE=0; LIMIT=0
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --from)         SRC="${2:-}"; shift 2 ;;
        --to)           DST="${2:-}"; shift 2 ;;
        --where)        WHERE="${2:-}"; shift 2 ;;
        --earliest)     EARLY="${2:-}"; shift 2 ;;
        --latest)       LATE="${2:-}"; shift 2 ;;
        --max-events)   LIMIT="${2:-}"; shift 2 ;;
        --execute)      EXEC=1; shift ;;
        --then-delete)  DELETE=1; shift ;;
        -h|--help)      usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
[ -n "$SRC" ] && [ -n "$DST" ] || usage 2
[ "$SRC" = "$DST" ] && im_die "--from and --to are the same index"
# A search term here is spliced into a search. Reject the characters that
# would end the intended search and start another.
case "$WHERE" in
    *'|'*|*'`'*|*'['*|*']'*)
        im_die "--where takes field terms only, not a pipeline: $WHERE" ;;
esac
im_resolve_user
im_require_auth

im_index_exists "$SRC" || im_die "the source index '$SRC' does not exist"
im_index_exists "$DST" || im_die "the destination index '$DST' does not exist; create it first with index-create.sh"

FILTER="index=$SRC${WHERE:+ $WHERE}"
im_head "What would move"
im_say "from        $SRC"
im_say "to          $DST"
im_say "matching    ${WHERE:-(everything in the window)}"
im_say "window      $EARLY .. $LATE"

COUNT_SEARCH="search $FILTER earliest=$EARLY latest=$LATE | stats count as n by sourcetype | sort - n"
OUT="$(im_splunk_auth "$COUNT_SEARCH -output csv -preview false")" || im_die "the count search failed"
printf '%s\n' "$OUT" | sed -n '2,$p' | sed 's/,/  /' | sed 's/^/    /'
TOTAL="$(printf '%s\n' "$OUT" | sed -n '2,$p' | awk -F, '{s+=$2} END{print s+0}')"
TOTAL="$(im_num "$TOTAL")"
im_say "total       $TOTAL event(s)"
[ "$TOTAL" -eq 0 ] && { echo; im_say "nothing matches; nothing to do."; exit 0; }

# A move re-indexes, so it is charged against the daily licence volume. A
# rough size is worth knowing before starting rather than afterwards.
SZ="$(im_splunk_auth "search $FILTER earliest=$EARLY latest=$LATE | eval b=len(_raw) | stats sum(b) as bytes -output csv -preview false" \
      | sed -n '2p' | tr -d '\r')"
SZ="$(im_num "${SZ%%.*}")"
[ "$SZ" -gt 0 ] && im_say "volume      about $(( SZ / 1048576 )) MB, which is charged against the licence again"

BEFORE="$(im_splunk_auth "search index=$DST earliest=$EARLY latest=$LATE | stats count -output csv -preview false" \
          | sed -n '2p' | tr -d '\r')"
BEFORE="$(im_num "$BEFORE")"
im_say "already in $DST for that window: $BEFORE event(s)"

if [ "$EXEC" != "1" ]; then
    echo
    im_say "This was a report. Re-run with --execute to move them."
    echo
    exit 0
fi

im_confirm "Re-index $TOTAL event(s) from $SRC into $DST. The originals stay where they are."

# collect writes the events to a spool file that Splunk's own batch input
# then reads, so the move completes after the search returns rather than
# during it. output_format=raw keeps the original event text intact.
MOVE="search $FILTER earliest=$EARLY latest=$LATE"
[ "$(im_num "$LIMIT")" -gt 0 ] && MOVE="$MOVE | head $LIMIT"
MOVE="$MOVE | collect index=$DST output_format=raw"
im_head "Moving"
im_splunk_auth "$MOVE -output csv -preview false" >/dev/null || im_die "the move search failed"
im_say "search finished; the spool is read asynchronously"

# Wait for the destination to actually grow. A collect that returns is not a
# collect that has been indexed, and reporting success on the search alone
# would be reporting the wrong thing.
im_head "Confirming it arrived"
WANT=$(( BEFORE + TOTAL ))
[ "$(im_num "$LIMIT")" -gt 0 ] && WANT=$(( BEFORE + LIMIT ))
for i in $(seq 1 30); do
    NOW="$(im_splunk_auth "search index=$DST earliest=$EARLY latest=$LATE | stats count -output csv -preview false" \
           | sed -n '2p' | tr -d '\r')"
    NOW="$(im_num "$NOW")"
    printf '\r  %s of %s event(s) in %s' "$NOW" "$WANT" "$DST"
    [ "$NOW" -ge "$WANT" ] && break
    sleep 10
done
echo
if [ "$(im_num "${NOW:-0}")" -ge "$WANT" ]; then
    im_say "all $TOTAL event(s) are in $DST"
else
    im_warn "expected $WANT in $DST, found ${NOW:-0}."
    im_warn "The spool may still be draining. Check the spool and splunkd.log:"
    im_warn "  ls $IM_SPLUNK_HOME/var/spool/splunk | head"
    im_warn "Do not delete anything from $SRC until the counts agree."
    exit 1
fi

if [ "$DELETE" = "1" ]; then
    echo
    im_warn "What 'delete' does in Splunk: it marks events unsearchable. It does"
    im_warn "not reclaim the disk they occupy and it cannot be undone. The space"
    im_warn "comes back only when the bucket is frozen on its own retention."
    im_warn "It needs a role holding the can_delete capability, which admin does"
    im_warn "not have by default."
    im_confirm "Mark the $TOTAL original event(s) in $SRC unsearchable?"
    im_splunk_auth "search $FILTER earliest=$EARLY latest=$LATE | delete -output csv -preview false" \
        | sed -n '1,4p' | sed 's/^/    /'
    im_say "done; verify with: index=$SRC $WHERE over the same window"
fi
echo
