#!/usr/bin/env bash
# Bring archived buckets back into an index so they can be searched again.
#
# When data passes an index's retention Splunk freezes it: with
# coldToFrozenDir set, the bucket is copied there and removed from the index;
# without it, the bucket is simply removed. Thawing puts a frozen bucket back
# into the index's thawedPath, where it is searchable again.
#
# Thawed data is not subject to the index's retention, so it stays until it
# is removed by hand. That is the point -- an investigation into last year
# should not have its evidence frozen out again mid-way -- but it also means
# thawedPath grows until someone empties it.
#
# A bucket frozen from an older Splunk may need its index rebuilt before it
# can be searched; --rebuild does that.
#
#   ./bin/index-thaw.sh --container splunk --index app_prod \
#       --from-archive /archive/app_prod --earliest 2026-01-01 --latest 2026-03-31
#   ./bin/index-thaw.sh --container splunk --index app_prod --list-thawed
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,24p' "$0"; exit "${1:-0}"; }
IDX=""; ARCHIVE=""; EARLY=""; LATE=""; REBUILD=0; LIST=0
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --index)        IDX="${2:-}"; shift 2 ;;
        --from-archive) ARCHIVE="${2:-}"; shift 2 ;;
        --earliest)     EARLY="${2:-}"; shift 2 ;;
        --latest)       LATE="${2:-}"; shift 2 ;;
        --rebuild)      REBUILD=1; shift ;;
        --list-thawed)  LIST=1; shift ;;
        -h|--help)      usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
[ -n "$IDX" ] || usage 2
im_resolve_user
im_index_exists "$IDX" || im_die "the index '$IDX' does not exist"

THAWED="$(im_index_setting "$IDX" thawedPath)"
THAWED="${THAWED//\$SPLUNK_DB/$IM_SPLUNK_HOME/var/lib/splunk}"
[ -n "$THAWED" ] || im_die "'$IDX' has no thawedPath; add one and restart"

if [ "$LIST" = "1" ]; then
    im_head "Already thawed in '$IDX'"
    im_say "thawedPath  $THAWED"
    OUT="$(im_run "ls -d '$THAWED'/* 2>/dev/null | sed 's#.*/##'")" || true
    if [ -z "$OUT" ]; then
        im_say "(empty)"
    else
        printf '%s\n' "$OUT" | while read -r b; do
            [ -n "$b" ] || continue
            newest="$(printf '%s' "$b" | awk -F_ '{print $2}')"
            oldest="$(printf '%s' "$b" | awk -F_ '{print $3}')"
            printf '    %-44s %s .. %s\n' "$b" \
                "$(date -u -d "@$(im_num "$oldest")" +'%F' 2>/dev/null || echo '?')" \
                "$(date -u -d "@$(im_num "$newest")" +'%F' 2>/dev/null || echo '?')"
        done
        k="$(im_num "$(im_run "du -sk '$THAWED' 2>/dev/null | cut -f1" | tr -d '\r')")"
        im_say "$(( k / 1024 )) MB, which no retention will remove"
    fi
    echo
    exit 0
fi

[ -n "$ARCHIVE" ] || im_die "--from-archive is required; it is where the frozen buckets are"
FROZEN_DIR="$(im_index_setting "$IDX" coldToFrozenDir)"
[ -n "$FROZEN_DIR" ] && im_say "the index freezes to  $FROZEN_DIR"

# A bucket's name carries the event times it holds, so the ones covering the
# period under investigation are selected without opening any of them.
E_EPOCH=0; L_EPOCH=9999999999
[ -n "$EARLY" ] && E_EPOCH="$(date -u -d "$EARLY" +%s 2>/dev/null)" || true
[ -n "$LATE" ]  && L_EPOCH="$(date -u -d "$LATE" +%s 2>/dev/null)" || true
E_EPOCH="$(im_num "$E_EPOCH")"; L_EPOCH="$(im_num "$L_EPOCH")"
[ "$L_EPOCH" -eq 0 ] && L_EPOCH=9999999999

im_head "Buckets in $ARCHIVE covering ${EARLY:-the beginning} .. ${LATE:-now}"
ALL="$(im_run "ls -d '$ARCHIVE'/db_* '$ARCHIVE'/*/db_* 2>/dev/null")" || true
[ -n "$ALL" ] || im_die "no buckets found under $ARCHIVE"

PICK="$(mktemp)"
while read -r b; do
    [ -n "$b" ] || continue
    name="$(basename "$b")"
    newest="$(im_num "$(printf '%s' "$name" | awk -F_ '{print $2}')")"
    oldest="$(im_num "$(printf '%s' "$name" | awk -F_ '{print $3}')")"
    [ "$newest" -lt "$E_EPOCH" ] && continue
    [ "$oldest" -gt "$L_EPOCH" ] && continue
    printf '%s\n' "$b" >> "$PICK"
    printf '    %-44s %s .. %s\n' "$name" \
        "$(date -u -d "@$oldest" +'%F' 2>/dev/null || echo '?')" \
        "$(date -u -d "@$newest" +'%F' 2>/dev/null || echo '?')"
done <<< "$ALL"

N="$(im_num "$(wc -l < "$PICK" 2>/dev/null)")"
im_say "$N bucket(s) selected of $(printf '%s\n' "$ALL" | grep -c . ) in the archive"
[ "$N" -eq 0 ] && { rm -f "$PICK"; im_say "nothing to thaw."; exit 0; }

if [ "$IM_DRY" = "1" ]; then
    rm -f "$PICK"; echo; im_say "dry run; nothing was thawed"; echo; exit 0
fi

im_confirm "Copy $N bucket(s) into $THAWED. They become searchable and no retention will remove them."

im_head "Thawing"
im_run "mkdir -p '$THAWED'"
OK=0
while read -r b; do
    [ -n "$b" ] || continue
    name="$(basename "$b")"
    # Copied, not moved: the archive stays intact, so a mistake here costs
    # disk rather than the only copy of the data.
    if im_run "cp -a '$b' '$THAWED/$name'" >/dev/null 2>&1 \
       && [ "$(im_num "$(im_run "test -d '$THAWED/$name' && echo 1 || echo 0" | tr -d '\r')")" -eq 1 ]; then
        [ "$REBUILD" = "1" ] && im_run "$IM_SPLUNK_HOME/bin/splunk rebuild '$THAWED/$name' '$IDX'" >/dev/null 2>&1
        OK=$(( OK + 1 ))
        printf '\r  %s of %s thawed' "$OK" "$N"
    else
        im_warn "could not thaw $name"
    fi
done < "$PICK"
echo
rm -f "$PICK"
im_run_root "chown -R $IM_USER '$THAWED'" >/dev/null 2>&1 || true

im_head "Making them searchable"
if im_splunkd_running; then
    im_say "asking splunkd to re-read the thawed path"
    im_splunk_auth "_internal call /data/indexes/$IDX/rebuild-metadata-and-manifests -method POST" \
        >/dev/null 2>&1 || im_warn "could not trigger a re-read; restart splunkd to pick them up"
else
    im_say "splunkd is stopped; they will be picked up when it starts"
fi
echo
im_say "$OK bucket(s) in $THAWED. Search the index over the thawed period to confirm."
im_say "When the investigation is over, remove them: they are outside retention."
echo
