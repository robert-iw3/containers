#!/usr/bin/env bash
# Create an index, or update the one you already have, in a named app.
#
# Index definitions are written to an app's local/indexes.conf rather than to
# etc/system/local, so the whole set can be versioned, copied to another
# instance, or removed as a unit.
#
# Retention is given in days and the cap in gigabytes, because that is how
# the question is asked. frozenTimePeriodInSecs and maxTotalDataSizeMB are
# what get written.
#
#   ./bin/index-create.sh --container splunk --index app_prod \
#       --retention-days 90 --cap-gb 50
#   ./bin/index-create.sh --container splunk --index app_prod --cap-gb 100 --restart
#
# Both limits are ceilings and whichever is reached first wins: an index with
# 90 days of retention and a 50 GB cap keeps 90 days only if 90 days fits in
# 50 GB. Leaving the cap unset does not make it unlimited -- it takes the
# default, which on most installations is 500 GB.
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,19p' "$0"; exit "${1:-0}"; }
IDX=""; APP="index_settings"; RET=""; CAP=""; RESTART=0; MAXHOT=""; COLD=""
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --index)          IDX="${2:-}"; shift 2 ;;
        --app)            APP="${2:-}"; shift 2 ;;
        --retention-days) RET="${2:-}"; shift 2 ;;
        --cap-gb)         CAP="${2:-}"; shift 2 ;;
        --max-hot)        MAXHOT="${2:-}"; shift 2 ;;
        --cold-to-frozen) COLD="${2:-}"; shift 2 ;;
        --restart)        RESTART=1; shift ;;
        -h|--help)        usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
[ -n "$IDX" ] || usage 2
case "$IDX" in
    _*) im_die "names beginning with an underscore are reserved for Splunk" ;;
    *[!a-zA-Z0-9_-]*) im_die "an index name takes letters, digits, hyphen and underscore only" ;;
esac
im_resolve_user

CONF="$IM_SPLUNK_HOME/etc/apps/$APP/local/indexes.conf"
EXISTS=0; im_index_exists "$IDX" && EXISTS=1

im_head "What is in force now"
if [ "$EXISTS" = "1" ]; then
    for k in homePath frozenTimePeriodInSecs maxTotalDataSizeMB maxHotBuckets coldToFrozenDir; do
        v="$(im_index_setting "$IDX" "$k")"
        [ -n "$v" ] && printf '  %-26s %s\n' "$k" "$v"
    done
    # Which file the current definition comes from, so a surprising value can
    # be traced rather than guessed at.
    src="$(im_run "$IM_SPLUNK_HOME/bin/splunk btool indexes list '$IDX' --debug 2>/dev/null \
            | sed -n 's/ *\[$IDX\].*//p' | sed -n 1p" | tr -d '\r')"
    [ -n "$src" ] && im_say "defined in  $src"
    # Two apps defining one index leaves precedence to decide which wins,
    # which is settled by app name rather than by intent.
    case "$src" in
        */apps/"$APP"/*) : ;;
        */apps/*)
            other="$(printf '%s' "$src" | sed 's#.*/apps/##; s#/.*##')"
            im_warn "already defined in the app '$other'."
            im_warn "Writing to '$APP' as well leaves two stanzas, and which one"
            im_warn "wins is decided by app precedence. Pass --app $other to edit"
            im_warn "the existing definition instead." ;;
    esac
else
    im_say "$IDX does not exist yet"
fi

STANZA="[$IDX]"
NEW=""
[ "$EXISTS" = "0" ] && {
    NEW="${NEW}homePath = \$SPLUNK_DB/$IDX/db
coldPath = \$SPLUNK_DB/$IDX/colddb
thawedPath = \$SPLUNK_DB/$IDX/thaweddb
"
}
[ -n "$RET" ] && {
    case "$RET" in ''|*[!0-9]*) im_die "--retention-days takes a whole number of days" ;; esac
    NEW="${NEW}frozenTimePeriodInSecs = $(( RET * 86400 ))
"
}
[ -n "$CAP" ] && {
    case "$CAP" in ''|*[!0-9]*) im_die "--cap-gb takes a whole number of gigabytes" ;; esac
    NEW="${NEW}maxTotalDataSizeMB = $(( CAP * 1024 ))
"
}
[ -n "$MAXHOT" ] && NEW="${NEW}maxHotBuckets = $MAXHOT
"
[ -n "$COLD" ] && NEW="${NEW}coldToFrozenDir = $COLD
"
[ -n "$NEW" ] || im_die "nothing to change; give --retention-days, --cap-gb, --max-hot or --cold-to-frozen"

im_head "What will be written to $CONF"
printf '%s\n' "$STANZA" | sed 's/^/  /'
printf '%s' "$NEW" | sed 's/^/  /'

[ "$IM_DRY" = "1" ] && { echo; im_say "dry run; nothing was written"; exit 0; }
im_confirm "This writes the stanza above. Data already indexed is not moved or deleted."

# Merge rather than append: appending a second stanza for the same index
# leaves two, and which one wins is not something to leave to file order.
TMP="$(mktemp)"
im_run "cat '$CONF' 2>/dev/null" > "$TMP" || true
python3 - "$TMP" "$IDX" <<'PY' > "$TMP.new"
import re, sys
path, idx = sys.argv[1], sys.argv[2]
try:
    txt = open(path).read()
except OSError:
    txt = ""
new = sys.stdin.read()
blocks = re.split(r'(?m)^(?=\[)', txt)
out, seen = [], False
for b in blocks:
    if b.strip().startswith(f"[{idx}]"):
        seen = True
        kept = {}
        for line in b.splitlines()[1:]:
            m = re.match(r'\s*([A-Za-z_.]+)\s*=\s*(.*)$', line)
            if m:
                kept[m.group(1)] = m.group(2)
        for line in new.splitlines():
            m = re.match(r'\s*([A-Za-z_.]+)\s*=\s*(.*)$', line)
            if m:
                kept[m.group(1)] = m.group(2)
        out.append(f"[{idx}]\n" + "".join(f"{k} = {v}\n" for k, v in kept.items()))
    elif b.strip():
        out.append(b if b.endswith("\n") else b + "\n")
if not seen:
    out.append(f"[{idx}]\n" + new)
sys.stdout.write("\n".join(x.rstrip("\n") for x in out) + "\n")
PY
im_run "mkdir -p '$(dirname "$CONF")'"
if [ -n "$IM_CONTAINER" ]; then
    podman cp "$TMP.new" "$IM_CONTAINER:$CONF"
    im_run_root "chown $IM_USER '$CONF'"
else
    cp "$TMP.new" "$CONF"
fi
rm -f "$TMP" "$TMP.new"
im_say "written"

if [ "$RESTART" = "1" ]; then
    im_head "Restarting so the change takes effect"
    im_stop; im_start
    im_index_exists "$IDX" && im_say "$IDX is now defined" || im_warn "$IDX is still not defined; check $CONF"
else
    echo
    im_say "Not yet in force. Re-run with --restart, or reload without a restart:"
    im_say "  splunk _internal call /data/indexes/_reload -auth <user>:<password>"
fi
echo
