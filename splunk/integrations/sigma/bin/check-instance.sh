#!/usr/bin/env bash
# Check that an instance can actually run this integration.
#
# bin/preflight.py checks the rule set. This checks the instance, and the
# two are not the same question: a rule set can be perfect and still detect
# nothing because of how the instance is configured.
#
# Everything here is something that has already gone wrong once, silently:
#
#   - A [default] stanza in any app's inputs.conf is a default for every
#     input on the instance, not for that app's inputs. One add-on setting
#     "disabled = 1" there also disabled Splunk's own spool input, which is
#     what consumes summary indexing results. Searches ran, matched, fired
#     their summary index action, wrote a stash file -- and nothing ever
#     read it. No error anywhere.
#   - Concurrency smaller than the number of scheduled searches means the
#     scheduler defers them indefinitely and reports no failure.
#   - A missing destination index drops results on the floor.
#   - Structured-data parsing happens where the file is read. An add-on on
#     the indexer does nothing for files a forwarder reads.
#
#   ./bin/check-instance.sh --container epo-uat-indexer
#   ./bin/check-instance.sh --local --alert-index sigma_alerts
set -uo pipefail

CONTAINER=""
SPLUNK_HOME="/opt/splunk"
ALERT_INDEX="sigma_alerts"
KPI_INDEX="sigma_engine_kpi"
FAIL=0
WARN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --container)   CONTAINER="${2:-}"; shift 2 ;;
        --local)       CONTAINER=""; shift ;;
        --splunk-home) SPLUNK_HOME="${2:-}"; shift 2 ;;
        --alert-index) ALERT_INDEX="${2:-}"; shift 2 ;;
        -h|--help)     sed -n '2,24p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

run() {
    if [ -n "$CONTAINER" ]; then
        local acct
        acct=$(podman exec "$CONTAINER" sh -c 'ps -o user= -p 1' 2>/dev/null | tr -d ' ')
        podman exec -u "${acct:-splunk}" "$CONTAINER" sh -c "$1" 2>/dev/null
    else
        sh -c "$1" 2>/dev/null
    fi
}

ok()   { printf '  ok       %s\n' "$1"; }
warn() { printf '  WARNING  %s\n' "$1"; WARN=$((WARN+1)); }
bad()  { printf '  FAILED   %s\n' "$1"; FAIL=$((FAIL+1)); }

echo
echo "  Instance: ${CONTAINER:-this host}"
echo

# --- 1. Any app imposing a global input default ----------------------
# This is the one that cost the most to find, so it is checked first.
globals=$(run "for f in $SPLUNK_HOME/etc/apps/*/local/inputs.conf $SPLUNK_HOME/etc/apps/*/default/inputs.conf $SPLUNK_HOME/etc/system/local/inputs.conf; do
  [ -f \"\$f\" ] || continue
  awk '/^\[default\]/{d=1;next} /^\[/{d=0} d&&/disabled[[:space:]]*=[[:space:]]*1/{print FILENAME; exit}' \"\$f\"
done")
if [ -n "$globals" ]; then
    bad "an app sets [default] disabled = 1 in inputs.conf, which disables every input on the instance:"
    echo "$globals" | sed 's|^|           |'
    echo "           name each stanza explicitly instead"
else
    ok "no app imposes a global input default"
fi

# --- 2. The spool input that consumes summary indexing ---------------
spool=$(run "$SPLUNK_HOME/bin/splunk btool inputs list --debug | grep -A6 'batch://.*var/spool/splunk\]' | grep -c 'disabled = 1'")
if [ "${spool:-0}" -gt 0 ]; then
    bad "the spool input is disabled; summary indexing will write stash files that nothing reads"
else
    ok "the spool input is enabled"
fi

stale=$(run "ls -1 $SPLUNK_HOME/var/spool/splunk/*.stash_new 2>/dev/null | wc -l")
if [ "${stale:-0}" -gt 2 ]; then
    warn "$stale unconsumed stash file(s) in the spool -- summary results are backing up"
else
    ok "the spool is draining (${stale:-0} file(s) pending)"
fi

# --- 3. Scheduled search concurrency ---------------------------------
cpus=$(run "nproc")
percpu=$(run "$SPLUNK_HOME/bin/splunk btool limits list search | sed -nE 's/^max_searches_per_cpu *= *([0-9]+)/\1/p' | tail -1")
base=$(run "$SPLUNK_HOME/bin/splunk btool limits list search | sed -nE 's/^base_max_searches *= *([0-9]+)/\1/p' | tail -1")
total=$(( ${percpu:-1} * ${cpus:-1} + ${base:-6} ))
slots=$(( total / 2 ))
sched=$(run "$SPLUNK_HOME/bin/splunk btool savedsearches list | grep -c '^\[Sigma Engine'")
printf '  ok       concurrency: %s per cpu x %s cpu + %s base = %s total, about %s for scheduled searches\n' \
    "${percpu:-1}" "${cpus:-1}" "${base:-6}" "$total" "$slots"
if [ "${sched:-0}" -gt "$slots" ]; then
    warn "$sched engine search(es) against about $slots slot(s): they must be spread across their interval, not fired together"
else
    ok "$sched engine search(es) fit the available slots"
fi

# --- 4. Destination indexes ------------------------------------------
for idx in "$ALERT_INDEX" "$KPI_INDEX"; do
    if [ "$(run "$SPLUNK_HOME/bin/splunk btool indexes list '$idx' | grep -c homePath")" -gt 0 ]; then
        ok "index $idx is defined"
    else
        bad "index $idx is not defined; results written to it are dropped"
    fi
done

# --- 5. Parsing happens where the file is read -----------------------
# An add-on on the indexer does nothing for a file a forwarder reads.
if [ "$(run "$SPLUNK_HOME/bin/splunk btool props list --debug | grep -c 'INDEXED_EXTRACTIONS'")" -gt 0 ]; then
    ok "structured-data extraction is configured here"
    warn "if the files are read by a forwarder, the same add-on must be installed there too"
else
    warn "no INDEXED_EXTRACTIONS on this instance; if it reads event XML from files, fields will be missing"
fi

echo
if [ "$FAIL" -gt 0 ]; then
    printf '  %s failure(s), %s warning(s) -- the instance cannot run the engine as configured\n\n' "$FAIL" "$WARN"
    exit 1
fi
printf '  ready: %s warning(s)\n\n' "$WARN"
