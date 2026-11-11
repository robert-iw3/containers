#!/usr/bin/env bash
# Move every bucket from one index to another, on disk, without re-indexing.
#
# Use this to consolidate two indexes or to complete a rename. Nothing is
# re-read or re-parsed, so it does not touch the licence, it keeps _indextime
# as it was, and it takes about as long as moving files takes.
#
# What it requires, and why:
#
#   splunkd stopped     a bucket being written cannot be moved out from
#                       under the process writing it.
#   hot buckets rolled  a hot bucket is open and is not a complete bucket.
#                       --roll-hot rolls them to warm first, which needs
#                       credentials and a running splunkd.
#   unique bucket ids   the number at the end of a bucket's name identifies
#                       it within its index. Two buckets with the same id in
#                       one index is corruption, so each moved bucket is
#                       renumbered above the highest already in the
#                       destination.
#
# Not for an indexer cluster: there, buckets carry a guid and are tracked by
# the manager, and moving them behind its back makes the cluster disagree
# with the disk. On a cluster, use the documented data rebalance instead.
#
#   ./bin/index-move-buckets.sh --container splunk --from old --to new --dry-run
#   ./bin/index-move-buckets.sh --container splunk --from old --to new \
#       --roll-hot --auth-file ~/.splunk-auth --stop-start
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,30p' "$0"; exit "${1:-0}"; }
SRC=""; DST=""; ROLL=0; STOPSTART=0; COPY=0
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --from)       SRC="${2:-}"; shift 2 ;;
        --to)         DST="${2:-}"; shift 2 ;;
        --roll-hot)   ROLL=1; shift ;;
        --stop-start) STOPSTART=1; shift ;;
        --copy)       COPY=1; shift ;;
        -h|--help)    usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
[ -n "$SRC" ] && [ -n "$DST" ] || usage 2
[ "$SRC" = "$DST" ] && im_die "--from and --to are the same index"
im_resolve_user
im_index_exists "$SRC" || im_die "the source index '$SRC' does not exist"
im_index_exists "$DST" || im_die "the destination index '$DST' does not exist; create it first"

SRC_HOME="$(im_index_path "$SRC")"; SRC_BASE="${SRC_HOME%/db}"
DST_HOME="$(im_index_path "$DST")"; DST_BASE="${DST_HOME%/db}"

# A clustered bucket carries a guid after its id. Moving those behind the
# manager's back is how a cluster ends up disagreeing with its own disk.
NRB="$(im_num "$(im_run "ls -d '$SRC_BASE'/db/rb_* 2>/dev/null | wc -l" | tr -d '\r')")"
[ "$NRB" -gt 0 ] && im_die \
    "$SRC holds $NRB replicated bucket(s); this is a clustered index. Use data rebalance."

im_head "Source and destination"
im_say "from  $SRC   $SRC_BASE"
im_say "to    $DST   $DST_BASE"

HOT="$(im_num "$(im_run "ls -d '$SRC_BASE'/db/hot_* 2>/dev/null | wc -l" | tr -d '\r')")"
if [ "$HOT" -gt 0 ]; then
    im_say "$SRC has $HOT hot bucket(s)"
    if [ "$ROLL" = "1" ]; then
        im_splunkd_running || im_die "--roll-hot needs splunkd running"
        im_require_auth
        im_head "Rolling hot buckets to warm"
        im_splunk_auth "_internal call /data/indexes/$SRC/roll-hot-buckets -method POST" \
            | sed -n '1,3p' | sed 's/^/    /'
        for i in $(seq 1 18); do
            HOT="$(im_num "$(im_run "ls -d '$SRC_BASE'/db/hot_* 2>/dev/null | wc -l" | tr -d '\r')")"
            printf '\r  %s hot bucket(s) remaining' "$HOT"
            [ "$HOT" -eq 0 ] && break
            sleep 5
        done
        echo
    fi
    [ "$HOT" -gt 0 ] && im_warn "$HOT hot bucket(s) will be left behind; pass --roll-hot to move them too"
fi

# The highest id already in the destination. Everything moved is numbered
# above it, in one pass, so no moved bucket can collide with another.
next_id() {
    local m
    m="$(im_run "ls -d '$DST_BASE'/db/db_* '$DST_BASE'/colddb/db_* 2>/dev/null \
         | sed 's#.*/##' | awk -F_ '{print \$4}' | sort -n | tail -1" | tr -d '\r')"
    printf '%s' "$(( $(im_num "$m") + 1 ))"
}
ID="$(next_id)"

PLAN="$(mktemp)"
for tier in db colddb; do
    LIST="$(im_run "ls -d '$SRC_BASE/$tier'/db_* 2>/dev/null")" || true
    while read -r b; do
        [ -n "$b" ] || continue
        name="$(basename "$b")"
        newest="$(printf '%s' "$name" | awk -F_ '{print $2}')"
        oldest="$(printf '%s' "$name" | awk -F_ '{print $3}')"
        printf '%s\t%s\t%s\n' "$tier" "$b" "db_${newest}_${oldest}_${ID}" >> "$PLAN"
        ID=$(( ID + 1 ))
    done <<< "$LIST"
done

N="$(im_num "$(wc -l < "$PLAN")")"
im_head "Plan: $N bucket(s)"
if [ "$N" -eq 0 ]; then
    rm -f "$PLAN"
    im_say "nothing to move."
    exit 0
fi
awk -F'\t' '{n=$2; sub(/.*\//,"",n); printf "    %-12s %-40s -> %s\n", $1, n, $3}' "$PLAN" | head -25
[ "$N" -gt 25 ] && im_say "    ... and $(( N - 25 )) more"

KB="$(im_num "$(im_run "du -sk '$SRC_BASE/db' '$SRC_BASE/colddb' 2>/dev/null | awk '{s+=\$1} END{print s+0}'" | tr -d '\r')")"
im_say "about $(( KB / 1024 )) MB"

if [ "$IM_DRY" = "1" ]; then
    rm -f "$PLAN"
    echo; im_say "dry run; nothing was moved"; echo
    exit 0
fi

if im_splunkd_running; then
    [ "$STOPSTART" = "1" ] || im_die \
        "splunkd is running. Stop it first, or pass --stop-start to have this do it."
fi

im_confirm "Move $N bucket(s) of $SRC into $DST. $SRC keeps its definition but loses its data."

STARTED=0
if im_splunkd_running; then im_stop; STARTED=1; fi

im_head "Moving"
MOVED=0; FAILED=0
while IFS="$(printf '\t')" read -r tier src newname; do
    [ -n "$tier" ] || continue
    dest="$DST_BASE/$tier/$newname"
    im_run "mkdir -p '$DST_BASE/$tier'"
    if [ "$COPY" = "1" ]; then
        op="cp -a '$src' '$dest'"
    else
        op="mv '$src' '$dest'"
    fi
    if im_run "$op" >/dev/null 2>&1; then
        # Assert the destination exists: a move that reports nothing is not
        # a move that happened.
        if [ "$(im_num "$(im_run "test -d '$dest' && echo 1 || echo 0" | tr -d '\r')")" -eq 1 ]; then
            MOVED=$(( MOVED + 1 ))
        else
            im_warn "reported success but $dest is not there: $(basename "$src")"
            FAILED=$(( FAILED + 1 ))
        fi
    else
        im_warn "could not move $(basename "$src")"
        FAILED=$(( FAILED + 1 ))
    fi
    printf '\r  %s of %s moved' "$MOVED" "$N"
done < "$PLAN"
echo
rm -f "$PLAN"

im_run_root "chown -R $IM_USER '$DST_BASE'" >/dev/null 2>&1 || true

# The manifest lists the buckets an index had. Leaving a stale one makes
# splunkd look for buckets that are no longer there; it is rebuilt on start.
im_run "rm -f '$SRC_BASE/db/.bucketManifest' '$DST_BASE/db/.bucketManifest'" >/dev/null 2>&1 || true
im_run "rm -f '$SRC_BASE/colddb/.bucketManifest' '$DST_BASE/colddb/.bucketManifest'" >/dev/null 2>&1 || true
im_say "bucket manifests cleared; splunkd rebuilds them on start"

[ "$STARTED" = "1" ] && im_start

im_head "Result"
im_say "moved   $MOVED"
[ "$FAILED" -gt 0 ] && im_warn "failed  $FAILED"
for i in "$SRC" "$DST"; do
    h="$(im_index_path "$i")"; b="${h%/db}"
    n="$(im_num "$(im_run "ls -d '$b'/db/db_* '$b'/colddb/db_* 2>/dev/null | wc -l" | tr -d '\r')")"
    k="$(im_num "$(im_run "du -sk '$b' 2>/dev/null | cut -f1" | tr -d '\r')")"
    printf '  %-26s %s bucket(s)  %s MB\n' "$i" "$n" "$(( k / 1024 ))"
done
echo
im_say "Searches over $DST should now find the moved data. If they do not, check"
im_say "  $IM_SPLUNK_HOME/var/log/splunk/splunkd.log for bucket errors."
[ "$FAILED" -gt 0 ] && exit 1
echo
