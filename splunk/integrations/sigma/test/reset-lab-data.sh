#!/usr/bin/env bash
# Empty a lab index and re-ingest only the data that parses correctly.
#
# Getting the parsing right took four passes, and each pass left a full
# copy of the events in the index. Only the last copy has the fields the
# rules need; the earlier ones carry an EventCode and nothing else. They
# can never match a rule, but every search still reads them, so they are
# pure cost -- here, roughly four times the volume for one copy of the
# answer.
#
# This uses "splunk clean eventdata", which is the supported way to empty
# an index. It requires splunkd to be stopped, which is why the script
# stops and starts it rather than asking you to.
#
#   ./bin/reset-lab-data.sh --container epo-uat-indexer --index linux_lab
#   ./bin/reset-lab-data.sh --container epo-uat-indexer --index linux_lab \
#       --uf epo-uat-uf --restage
#
# WHAT IS LOST. Everything in the named index, which on this lab is
# generated test data plus whatever the forwarder collected from its own
# host. Nothing else is touched: other indexes, the detections in
# sigma_alerts, the case journal and all configuration are left alone.
# There is no undo, so the index is named explicitly and never defaulted.
set -euo pipefail

CONTAINER=""
UF=""
INDEX=""
RESTAGE=0
ASSUME_YES=0

usage() { sed -n '2,24p' "$0"; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --container) CONTAINER="${2:-}"; shift 2 ;;
        --uf)        UF="${2:-}"; shift 2 ;;
        --index)     INDEX="${INDEX:+$INDEX,}${2:-}"; shift 2 ;;
        --restage)   RESTAGE=1; shift ;;
        --yes)       ASSUME_YES=1; shift ;;
        -h|--help)   usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done

[ -n "$INDEX" ] || { echo "FAIL: --index is required and is never defaulted" >&2; exit 2; }
[ -n "$CONTAINER" ] || { echo "FAIL: --container is required" >&2; exit 2; }

acct=$(podman exec "$CONTAINER" sh -c 'ps -o user= -p 1' 2>/dev/null | tr -d ' ')
acct="${acct:-splunk}"
run() { podman exec -u "$acct" "$CONTAINER" sh -c "$1"; }

echo
echo "  index:     $INDEX"
echo "  instance:  $CONTAINER (service account $acct)"
for ix in $(echo "$INDEX" | tr ',' ' '); do
    run "du -sh /opt/splunk/var/lib/splunk/$ix 2>/dev/null || true" | sed "s/^/  size:      /"
done
echo

if [ "$ASSUME_YES" -ne 1 ]; then
    printf '  This empties %s permanently. Type the index name(s) to continue: ' "$INDEX"
    read -r reply
    [ "$reply" = "$INDEX" ] || { echo "  not confirmed; nothing was changed"; exit 1; }
fi

echo "  stopping splunkd"
run "/opt/splunk/bin/splunk stop" >/dev/null 2>&1 || true

echo "  emptying the index(es)"
IFS=',' read -ra IDXS <<< "$INDEX"
for ix in "${IDXS[@]}"; do
    [ -n "$ix" ] || continue
    echo "    $ix"
    run "/opt/splunk/bin/splunk clean eventdata -index $ix -f" 2>&1 | sed 's/^/      /' || {
        echo "  FAIL: clean eventdata did not succeed for $ix; restarting splunkd" >&2
        run "/opt/splunk/bin/splunk start" >/dev/null 2>&1 || true
        exit 1
    }
done

echo "  starting splunkd"
run "/opt/splunk/bin/splunk start" >/dev/null 2>&1 || true
for ix in $(echo "$INDEX" | tr ',' ' '); do
    run "du -sh /opt/splunk/var/lib/splunk/$ix 2>/dev/null || true" | sed "s/^/  size now:  /"
done

if [ -n "$UF" ]; then
    echo
    echo "  pruning the monitor inputs validation rounds left behind"
    python3 "$(dirname "$0")/prune-round-inputs.py" --container "$UF" 2>&1 | sed 's/^/  /' || true
fi

if [ "$RESTAGE" -eq 1 ] && [ -n "$UF" ]; then
    echo
    echo "  re-reading the staged data on $UF"
    # The fishbucket remembers what it has read, and the index no longer
    # holds it, so the two have to be put back in step. Resetting the
    # forwarder's checkpoint is what makes the files be read again.
    podman exec -u root "$UF" sh -c '
        LAB=/opt/splunkforwarder/etc/apps/sigma_lab_inputs/lab-logs
        acct=$(ps -o user= -p 1 | tr -d " ")
        /opt/splunkforwarder/bin/splunk stop >/dev/null 2>&1 || true
        rm -rf /opt/splunkforwarder/var/lib/splunk/fishbucket
        chown -R "${acct:-ansible}" /opt/splunkforwarder/var/lib/splunk 2>/dev/null || true
        /opt/splunkforwarder/bin/splunk start >/dev/null 2>&1 || true
    ' 2>&1 | sed 's/^/    /'
    echo "    the forwarder will re-read every enabled input from the start"
fi

echo
echo "  done. Only the enabled inputs will repopulate the index."
echo
