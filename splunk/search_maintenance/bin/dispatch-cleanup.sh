#!/usr/bin/env bash
# Search artifacts: what they are using, and removing the ones past their time.
#
# Every search that runs leaves a directory under
# $SPLUNK_HOME/var/run/splunk/dispatch holding its results. Splunk reaps them
# on each search's own ttl, but a reap that falls behind, a search with a long
# ttl, or a scheduler that has been retrying all night leaves a dispatch
# directory with hundreds of thousands of entries. The instance then slows
# down for reasons nothing reports, because the slowness is the filesystem.
#
# This reports before it removes, and removes only what you ask for.
#
#   ./bin/dispatch-cleanup.sh --container splunk
#   ./bin/dispatch-cleanup.sh --container splunk --older-than 7
#   ./bin/dispatch-cleanup.sh --container splunk --older-than 7 --delete
set -uo pipefail

CONTAINER=""
SPLUNK_HOME="${SPLUNK_HOME:-/opt/splunk}"
USER_NAME=""
OLDER=""
DELETE=0
TOP=15

usage() { sed -n '2,15p' "$0"; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
    case "$1" in
        --container)   CONTAINER="${2:-}"; shift 2 ;;
        --splunk-home) SPLUNK_HOME="${2:-}"; shift 2 ;;
        --user)        USER_NAME="${2:-}"; shift 2 ;;
        --older-than)  OLDER="${2:-}"; shift 2 ;;
        --top)         TOP="${2:-}"; shift 2 ;;
        --delete)      DELETE=1; shift ;;
        -h|--help)     usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done

die()  { printf 'FAIL: %s\n' "$*" >&2; exit 2; }
say()  { printf '  %s\n' "$*"; }
head_() { printf '\n== %s ==\n' "$*"; }
num()  { case "${1:-}" in ''|*[!0-9]*) printf '0' ;; *) printf '%s' "$1" ;; esac; }

if [ -n "$CONTAINER" ]; then
    [ -n "$USER_NAME" ] || USER_NAME="$(podman exec "$CONTAINER" stat -c '%U' "$SPLUNK_HOME/etc" 2>/dev/null | tr -d '\r')"
    [ -n "$USER_NAME" ] || die "cannot read $SPLUNK_HOME/etc in $CONTAINER"
    run() { podman exec -u "$USER_NAME" "$CONTAINER" sh -c "$1"; }
else
    run() { sh -c "$1"; }
fi

D="$SPLUNK_HOME/var/run/splunk/dispatch"
run "test -d '$D'" || die "no dispatch directory at $D"

head_ "Search artifacts"
COUNT="$(num "$(run "ls -1 '$D' 2>/dev/null | wc -l" | tr -d ' \r')")"
KB="$(num "$(run "du -sk '$D' 2>/dev/null | cut -f1" | tr -d ' \r')")"
say "location  $D"
say "jobs      $COUNT"
say "size      $(( KB / 1024 )) MB"

# Each directory is named for the job that made it: scheduler__ for a
# scheduled run, admin__ and friends for someone's ad hoc search.
head_ "Where they came from"
run "ls -1 '$D' 2>/dev/null" | awk '
    /^scheduler__/ { sched++; next }
    /^rt_/         { rt++;    next }
    /^subsearch/   { sub_++;  next }
    { adhoc++ }
    END {
        printf "  scheduled  %d\n", sched
        printf "  ad hoc     %d\n", adhoc
        printf "  real-time  %d\n", rt
        printf "  subsearch  %d\n", sub_
    }'

head_ "Biggest consumers, by app"
# A scheduled job's directory is named scheduler__<owner>_<base64 app>__...
# Decoding that segment turns an unreadable name into the app responsible,
# which is the thing you need in order to act on this.
run "du -sk '$D'/* 2>/dev/null | sort -rn" | while read -r kb path; do
    name="$(basename "$path")"
    case "$name" in
        scheduler__*)
            rest="${name#scheduler__}"
            owner="${rest%%_*}"
            b64="${rest#*_}"; b64="${b64%%__*}"
            app="$(printf '%s' "$b64" | base64 -d 2>/dev/null)"
            [ -n "$app" ] || app="$b64"
            label="$app  (scheduled, $owner)" ;;
        rt_*)        label="real-time search" ;;
        subsearch*)  label="subsearch" ;;
        *)           label="${name%%_*}  (ad hoc)" ;;
    esac
    printf '%s\t%s\n' "$kb" "$label"
done | awk -F'\t' '
    { kb[$2] += $1; n[$2]++ }
    END { for (k in kb) printf "%d\t%d\t%s\n", kb[k], n[k], k }' \
  | sort -rn | head -"$TOP" \
  | awk -F'\t' '{ printf "  %8.1f MB  %5d job(s)  %s\n", $1/1024, $2, $3 }'

if [ -n "$OLDER" ]; then
    case "$OLDER" in ''|*[!0-9]*) die "--older-than takes a whole number of days" ;; esac
    head_ "Older than $OLDER day(s)"
    OLD_N="$(num "$(run "find '$D' -maxdepth 1 -mindepth 1 -type d -mtime +$OLDER 2>/dev/null | wc -l" | tr -d ' \r')")"
    OLD_KB="$(num "$(run "find '$D' -maxdepth 1 -mindepth 1 -type d -mtime +$OLDER -exec du -sk {} + 2>/dev/null | awk '{s+=\$1} END{print s+0}'" | tr -d ' \r')")"
    say "jobs  $OLD_N"
    say "size  $(( OLD_KB / 1024 )) MB"
    if [ "$OLD_N" -eq 0 ]; then
        echo
        say "nothing to remove."
        echo
        exit 0
    fi
    run "find '$D' -maxdepth 1 -mindepth 1 -type d -mtime +$OLDER 2>/dev/null | head -8" \
      | sed 's#.*/#      #'
    [ "$OLD_N" -gt 8 ] && say "      ... and $(( OLD_N - 8 )) more"

    if [ "$DELETE" != "1" ]; then
        echo
        say "This was a report. Add --delete to remove them."
        echo
        exit 0
    fi

    echo
    printf '  Remove %s job artifact(s), %s MB, permanently. Type yes: ' \
        "$OLD_N" "$(( OLD_KB / 1024 ))"
    read -r answer
    [ "$answer" = "yes" ] || { say "stopped."; exit 1; }

    # Splunk owns this directory; removing an artifact for a job that is
    # still running loses that job's results, so a running job is left alone.
    head_ "Removing"
    run "find '$D' -maxdepth 1 -mindepth 1 -type d -mtime +$OLDER \
         ! -exec test -f {}/status.csv.lock \; -print -exec rm -rf {} + 2>/dev/null | wc -l" \
      | sed 's/^/  removed: /'
    AFTER_KB="$(num "$(run "du -sk '$D' 2>/dev/null | cut -f1" | tr -d ' \r')")"
    say "size now $(( AFTER_KB / 1024 )) MB, was $(( KB / 1024 )) MB"
    echo
    say "Splunk reaps artifacts on each search's own ttl. If this directory"
    say "fills up again, the ttl is the thing to change, not this script."
fi
echo
