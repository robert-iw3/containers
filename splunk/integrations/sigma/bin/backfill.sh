#!/usr/bin/env bash
# Run the detection engine once over data that is already indexed.
#
# The engine looks at the last fifteen or thirty minutes, because a window
# wider than the interval re-reads the same events and writes the same
# detection again. That is right for a live feed and wrong on the day you
# install it: an instance with thirty days of logs sees nothing until new
# data arrives, and the dashboards read zero for a reason that has nothing
# to do with the rules.
#
# This runs the whole engine once across a window you choose, waits for
# every search to complete, and puts the production cadence back.
#
#   ./bin/backfill.sh --container epo-uat-indexer --window -7d
#   ./bin/backfill.sh --container epo-uat-indexer --window -24h --rules "<dirs>"
#
# It writes a detection for everything it finds in that window, so running
# it twice over the same period writes them twice. It is meant to be run
# once, after installing, and then not again.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER=""
APP="sigma_detection_lab"
WINDOW="-24h"
CRON="*/5 * * * *"
WAIT=1800
RULES="$HERE/rules-core/SigmaHQ_sigma/core/rules/windows/process_creation $HERE/rules-core/SigmaHQ_sigma/core/rules/linux"

usage() { sed -n '2,18p' "$0"; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
    case "$1" in
        --container) CONTAINER="${2:-}"; shift 2 ;;
        --window)    WINDOW="${2:-}"; shift 2 ;;
        --cron)      CRON="${2:-}"; shift 2 ;;
        --rules)     RULES="${2:-}"; shift 2 ;;
        --wait)      WAIT="${2:-}"; shift 2 ;;
        -h|--help)   usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done
[ -n "$CONTAINER" ] || { echo "FAIL: --container is required" >&2; exit 2; }

export PYTHONPATH="$HERE/pylib:${PYTHONPATH:-}"
SP="$(mktemp -d)"
trap 'rm -rf -- "$SP"' EXIT

deploy() {  # $1 = description
    rm -rf "$SP/stage"; mkdir -p "$SP/stage"
    tar -C "$HERE/app" --exclude='local' --exclude='local.meta' -cf - "$APP" \
        | tar -C "$SP/stage" -xf -
    local S="$SP/stage/$APP/default/savedsearches.conf"
    printf '\n' >> "$S"
    cat "$SP/stage/$APP/default/savedsearches_engine.conf" >> "$S"
    find "$SP/stage" -name savedsearches_engine.conf -delete
    tar -C "$SP/stage" -czf "$SP/app.tgz" "$APP"
    podman cp "$SP/app.tgz" "$CONTAINER:/tmp/backfill-app.tgz"
    podman exec -u splunk "$CONTAINER" rm -rf "/opt/splunk/etc/apps/$APP/default"
    podman exec -u splunk "$CONTAINER" rm -rf "/opt/splunk/etc/apps/$APP/lookups"
    podman exec -u splunk -w /opt/splunk/etc/apps "$CONTAINER" tar -xzf /tmp/backfill-app.tgz
    podman exec -u splunk "$CONTAINER" sh -c '/opt/splunk/bin/splunk restart >/dev/null 2>&1'
    echo "  $1"
}

echo
echo "== 1. Build the engine with a $WINDOW window =="
python3 "$HERE/bin/build-engine.py" $RULES --window "$WINDOW" --cron "$CRON" 2>&1 \
    | sed -n '/batched search/p'
deploy "deployed for backfill"

echo
echo "== 2. Wait for every search to run once =="
# Only the detection searches. The rollups run once a day, so counting them
# here makes the target unreachable and the wait always runs to its timeout.
want=$(podman exec -u splunk "$CONTAINER" sh -c \
    "grep -cE '^\[Sigma (Engine|Rule) - ' /opt/splunk/etc/apps/$APP/default/savedsearches.conf")
start=$(date +%s)
deadline=$(( start + WAIT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    done_n=$(podman exec -u splunk "$CONTAINER" sh -c \
      "awk -v s=$start '\$0 ~ /status=success/ && /savedsearch_name=\"Sigma (Engine|Rule) - /' /opt/splunk/var/log/splunk/scheduler.log 2>/dev/null \
       | grep -oE 'savedsearch_name=\"[^\"]+\"' | sort -u | wc -l" || echo 0)
    printf '\r  %s of %s search(es) have run' "${done_n:-0}" "$want"
    [ "${done_n:-0}" -ge "$want" ] && break
    sleep 20
done
echo

echo
echo "== 3. Restore the production cadence =="
python3 "$HERE/bin/build-engine.py" $RULES 2>&1 | sed -n '/batched search/p'
deploy "production cadence restored"

echo
podman exec -u splunk "$CONTAINER" sh -c \
  'du -sh /opt/splunk/var/lib/splunk/sigma_alerts 2>/dev/null' | sed 's/^/  detections: /'
echo
