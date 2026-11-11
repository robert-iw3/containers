#!/usr/bin/env bash
# Rename an index -- which Splunk cannot do, so this does what a rename is.
#
# There is no rename. An index name is in its stanza, in the bucket paths, in
# every input that routes to it, and in every search, dashboard and alert
# that names it. So a rename is four things:
#
#   1. a new index with the old one's settings
#   2. its data moved across, on disk, without re-indexing
#   3. everything that referenced the old name repointed
#   4. the old definition removed
#
# This does 1 and 2, reports everything it can find for 3, and leaves 4 to
# you. Step 3 is the one that breaks deployments: the data moves silently and
# the searches keep looking at a name that no longer holds anything.
#
#   ./bin/index-rename.sh --container splunk --from old_name --to new_name --dry-run
#   ./bin/index-rename.sh --container splunk --from old_name --to new_name \
#       --auth-file ~/.splunk-auth --execute
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$(cd "$HERE/../lib" && pwd)/common.sh"

usage() { sed -n '2,22p' "$0"; exit "${1:-0}"; }
SRC=""; DST=""; APP="index_settings"; EXEC=0; AUTHFILE=""
ARGS=("$@")
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --from)    SRC="${2:-}"; shift 2 ;;
        --to)      DST="${2:-}"; shift 2 ;;
        --app)     APP="${2:-}"; shift 2 ;;
        --execute) EXEC=1; shift ;;
        -h|--help) usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
[ -n "$SRC" ] && [ -n "$DST" ] || usage 2
im_resolve_user
im_index_exists "$SRC" || im_die "the source index '$SRC' does not exist"

# Pass the connection flags through to the scripts this one calls.
PASS=(--splunk-home "$IM_SPLUNK_HOME")
[ -n "$IM_CONTAINER" ] && PASS+=(--container "$IM_CONTAINER")
[ -n "$IM_USER" ]      && PASS+=(--user "$IM_USER")
for a in "${ARGS[@]}"; do
    [ "$a" = "--auth-file" ] && AUTHFILE="next" && continue
    [ "$AUTHFILE" = "next" ] && { PASS+=(--auth-file "$a"); AUTHFILE=""; }
done

im_head "1. The settings to carry over"
RET="$(im_num "$(im_index_setting "$SRC" frozenTimePeriodInSecs)")"
CAP="$(im_num "$(im_index_setting "$SRC" maxTotalDataSizeMB)")"
im_say "retention  $(( RET / 86400 )) day(s)"
im_say "cap        $CAP MB"

# --- 3 first, because it decides whether the rest is safe ----------------
# A name is referenced from configuration and from saved knowledge objects.
# Finding them after the data has moved is finding them too late.
im_head "What still refers to '$SRC'"
FOUND=0
scan() {  # $1 label, $2 find expression
    local out
    out="$(im_run "$2" 2>/dev/null)" || true
    if [ -n "$out" ]; then
        printf '  %s\n' "$1"
        printf '%s\n' "$out" | sed 's/^/      /' | head -20
        FOUND=1
    fi
}
scan "configuration files" \
    "grep -rl --include='*.conf' -w '$SRC' $IM_SPLUNK_HOME/etc/apps $IM_SPLUNK_HOME/etc/system/local 2>/dev/null | sed 's#$IM_SPLUNK_HOME/etc/##'"
scan "saved searches, macros and dashboards naming it" \
    "grep -rl -w 'index=$SRC' $IM_SPLUNK_HOME/etc/apps 2>/dev/null | sed 's#$IM_SPLUNK_HOME/etc/##'"
if [ "$FOUND" = "0" ]; then
    im_say "nothing found. That is worth a second look: an index with data"
    im_say "usually has an input routing to it."
else
    echo
    im_warn "These keep pointing at '$SRC' after the data has gone. Repoint them,"
    im_warn "and remember that anything outside this instance -- a forwarder's"
    im_warn "inputs.conf, a search in another app, an external dashboard -- will"
    im_warn "not appear in this list."
fi

if [ "$EXEC" != "1" ]; then
    im_head "Plan"
    im_say "1. create '$DST' with the settings above"
    im_say "2. move every bucket of '$SRC' into it"
    im_say "3. repoint the references listed above (yours to do)"
    im_say "4. remove the '$SRC' definition once you are satisfied (yours to do)"
    echo
    im_say "Re-run with --execute to do 1 and 2."
    echo
    exit 0
fi

im_head "Creating '$DST'"
CREATE=("$HERE/index-create.sh" "${PASS[@]}" --index "$DST" --app "$APP" --yes --restart)
[ "$RET" -gt 0 ] && CREATE+=(--retention-days "$(( RET / 86400 ))")
[ "$CAP" -gt 0 ] && CREATE+=(--cap-gb "$(( CAP / 1024 ))")
"${CREATE[@]}" || im_die "could not create '$DST'"

im_head "Moving the data"
bash "$HERE/index-move-buckets.sh" "${PASS[@]}" --from "$SRC" --to "$DST" \
    --roll-hot --stop-start --yes || im_die "the bucket move did not finish cleanly"

im_head "Still to do, by hand"
im_say "1. repoint everything listed above from '$SRC' to '$DST'"
im_say "2. on each forwarder, change inputs.conf and restart it"
im_say "3. confirm new data arrives in '$DST' before removing '$SRC'"
im_say "4. remove the '$SRC' stanza, then restart"
echo
im_say "Until step 2 is done, new data still arrives in '$SRC'."
echo
