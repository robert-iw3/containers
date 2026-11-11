#!/usr/bin/env bash
# Collect the field names an environment actually produces.
#
# A Sigma rule keyed on Image matches nothing where Image is never
# extracted, and the result is indistinguishable from a quiet network. The
# inventory this writes lets bin/preflight.py answer that question before a
# rule set is deployed rather than after.
#
#   ./bin/field-inventory.sh --container epo-uat-indexer --index linux_lab
#   ./bin/field-inventory.sh --local --index main > planning/available-fields.txt
#
# Fields are read from the add-on configuration rather than from the data,
# so the answer does not depend on whether a matching event happened to
# arrive recently. That matters: an inventory built from a quiet hour would
# report fields as missing that are merely idle.
set -euo pipefail

CONTAINER=""
SPLUNK_HOME_DEFAULT="/opt/splunk"
INDEX=""
OUT=""

usage() { sed -n '2,18p' "$0"; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --container) CONTAINER="${2:-}"; shift 2 ;;
        --local)     CONTAINER=""; shift ;;
        --index)     INDEX="${2:-}"; shift 2 ;;
        --splunk-home) SPLUNK_HOME_DEFAULT="${2:-}"; shift 2 ;;
        --out)       OUT="${2:-}"; shift 2 ;;
        -h|--help)   usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done

run() {
    if [ -n "$CONTAINER" ]; then
        # The service account owns $SPLUNK_HOME; running the CLI as another
        # user rewrites ownership and breaks the next restart.
        local acct
        acct=$(podman exec "$CONTAINER" sh -c 'ps -o user= -p 1' 2>/dev/null | tr -d ' ')
        podman exec -u "${acct:-splunk}" "$CONTAINER" sh -c "$1"
    else
        sh -c "$1"
    fi
}

emit() {
    {
        echo "# Fields this environment produces."
        echo "# Collected $(date -u +%Y-%m-%dT%H:%M:%SZ) from ${CONTAINER:-this host}."
        echo "#"
        echo "# Index-time extractions are listed as the add-on declares them;"
        echo "# search-time extractions come from EXTRACT, REPORT and FIELDALIAS."

        # Explicit extractions and aliases, from every loaded app.
        run "$SPLUNK_HOME_DEFAULT/bin/splunk btool props list --debug 2>/dev/null" \
          | sed -E 's/^[^ ]+ +//' \
          | grep -E '^(EXTRACT-|REPORT-|FIELDALIAS-|EVAL-|LOOKUP-)' \
          | sed -E 's/^EVAL-([A-Za-z0-9_]+).*/\1/; s/^FIELDALIAS-[^=]*= *//; s/^(EXTRACT|REPORT|LOOKUP)-[^=]*= *//' \
          | tr ' ,' '\n\n' \
          | sed -E 's/.*\bAS\b *//I' \
          | grep -E '^[A-Za-z_][A-Za-z0-9_.]*$' || true

        # Named capture groups in transforms: these are the field names a
        # REPORT actually yields.
        run "$SPLUNK_HOME_DEFAULT/bin/splunk btool transforms list --debug 2>/dev/null" \
          | grep -oE '\(\?<[A-Za-z_][A-Za-z0-9_]*>' \
          | sed -E 's/\(\?<//; s/>//' || true

        # FORMAT = $1::$2 transforms name their fields from the data, not
        # from the configuration, so those have to come from the index.
        if [ -n "$INDEX" ]; then
            run "$SPLUNK_HOME_DEFAULT/bin/splunk btool props list --debug 2>/dev/null" \
              | grep -oE 'INDEXED_EXTRACTIONS *= *[A-Za-z-]+' >/dev/null 2>&1 && {
                echo "# Index-time structured extraction is in use on this instance;"
                echo "# field names there come from the data and cannot be read from"
                echo "# configuration. Add any that matter by hand."
            }
        fi
    } | sed '/^#/!{s/^[[:space:]]*//; s/[[:space:]]*$//}' \
      | awk '/^#/ {print; next} NF && !seen[$0]++ {print}'
}

if [ -n "$OUT" ]; then
    emit > "$OUT"
    printf '  %s field name(s) -> %s\n' "$(grep -vc '^#' "$OUT" || echo 0)" "$OUT"
else
    emit
fi
