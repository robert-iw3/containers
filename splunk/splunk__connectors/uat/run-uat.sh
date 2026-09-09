#!/usr/bin/env bash
# Run the Splunk connectors against a HEC that enforces HEC's rules.
#
#   ./run-uat.sh                 every case
#   ./run-uat.sh csv-trellix     one case by name
#   KEEP_UP=1 ./run-uat.sh       leave the rig up for inspection
#
# Order matters and is not negotiable: the oracle is proved first, and a
# failure there aborts before a single connector result is recorded. A test
# whose oracle is broken produces verdicts, not evidence.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${HERE}/work"
DROP="${WORK}/drop"
HEC_TOKEN="${UAT_HEC_TOKEN:-uat-token}"
SETTLE="${UAT_SETTLE:-8}"

PASS=0; FAIL=0; SKIP=0
declare -a FAILURES=()

# Bash reads a numeric comparison operand as a variable name, so a non-numeric
# value aborts the run under set -u instead of comparing false. Coerce first.
num() { local v="${1:-}"; [[ "$v" =~ ^-?[0-9]+$ ]] && printf '%s' "$v" || printf '0'; }

say()  { printf '%s\n' "$*"; }
head2() { printf '\n=== %s ===\n' "$*"; }

ok()   { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf '  FAIL  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '          %s\n' "$2"; return 0; }
skip() { SKIP=$((SKIP+1)); printf '  skip  %s\n' "$1"; }

# ---------------------------------------------------------------- compose ---
if podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
else
    say "no podman compose provider found"; exit 2
fi

dc() { (cd "$HERE" && "${COMPOSE[@]}" "$@"); }

cleanup() {
    if [[ "${KEEP_UP:-0}" == "1" ]]; then
        say ""; say "KEEP_UP=1, rig left running. Tear down with: ${COMPOSE[*]} -f ${HERE}/compose.yaml down -v"
        return
    fi
    dc down >/dev/null 2>&1 || true
}
trap cleanup EXIT

# ------------------------------------------------------------------ set up ---
# Guards first: they need no containers and name a defect class outright,
# where the same bug reaches the integration cases only as a missing event.
head2 "static guards"
if "${HERE}/static_guards.sh"; then
    ok "static guards clear"
else
    bad "static guards tripped" "see the lines above"
fi

head2 "fixtures"
python3 "${HERE}/make_fixtures.py"

rm -rf "$WORK"; mkdir -p "$DROP"
: > "${WORK}/hec-events.jsonl"

head2 "build"
dc build >"${WORK}/build.log" 2>&1 || { say "build failed:"; tail -30 "${WORK}/build.log"; exit 2; }
say "image built"

head2 "bring up oracle"
dc up -d mock-hec >/dev/null 2>&1

# Readiness by health endpoint, not by sleeping.
ready=0
for _ in $(seq 1 30); do
    if podman exec connector-uat-hec \
        curl -sf "http://127.0.0.1:8088/services/collector/health" >/dev/null 2>&1; then
        ready=1; break
    fi
    sleep 1
done
[[ "$ready" == "1" ]] || { say "mock HEC never became ready"; podman logs connector-uat-hec 2>&1 | tail -20; exit 2; }
say "mock HEC ready"

# A limit written in compose but dropped by the provider is worse than no limit.
head2 "resource limits landed"
for c in connector-uat-hec; do
    mem="$(podman inspect -f '{{.HostConfig.Memory}}' "$c" 2>/dev/null || echo 0)"
    if [[ "$(num "$mem")" -gt 0 ]]; then
        ok "$c memory limit = $mem"
    else
        bad "$c has NO memory limit" "deploy.resources.limits was dropped by the compose provider"
    fi
done

# ------------------------------------------------------------ oracle first ---
head2 "oracle self-test (gates everything below)"
if podman exec connector-uat-hec python3 /uat/selftest_hec.py http://127.0.0.1:8088 "$HEC_TOKEN"; then
    ok "mock HEC enforces HEC semantics"
else
    say ""
    say "ABORT: the oracle does not enforce what it claims. No connector result below would mean anything."
    exit 3
fi

# ------------------------------------------------------------- core units ---
# Run before the integration cases: these decide time coercion, offset
# semantics and HEC framing, and a failure here explains an integration
# failure below rather than being explained by it.
head2 "core unit tests"
if podman exec connector-uat-hec python3 /uat/test_core.py >"${WORK}/units.log" 2>&1; then
    ok "core units ($(grep -cE '^test_' "${WORK}/units.log" || echo '?') tests)"
else
    bad "core unit tests failed" "see ${WORK}/units.log"
    sed -n '/FAIL:\|ERROR:/,+3p' "${WORK}/units.log" | sed -n '1,24p' || true
fi

# --------------------------------------------------------------- the cases ---
hec_reset() {
    podman exec connector-uat-hec \
        curl -sf -X POST "http://127.0.0.1:8088/__reset" >/dev/null 2>&1 || true
    : > "${WORK}/hec-events.jsonl" 2>/dev/null || true
}

hec_stat() {  # hec_stat <key>
    podman exec connector-uat-hec curl -sf "http://127.0.0.1:8088/__stats" 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$1', 0))" 2>/dev/null || printf '0'
}

hec_code_count() {  # hec_code_count <code>
    podman exec connector-uat-hec curl -sf "http://127.0.0.1:8088/__stats" 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('by_code',{}).get('$1',0))" 2>/dev/null || printf '0'
}

# run_case <name> <connector-path> <schemas> <fixture> <expected-accepted>
run_case() {
    local name="$1" connector="$2" schemas="$3" fixture="$4" expect="$5"

    head2 "case: ${name}"
    hec_reset
    rm -f "${DROP}"/* 2>/dev/null || true
    # Offsets too: a case that inherits the previous case's state is not
    # testing what it claims, and the resume case below covers that path
    # deliberately rather than by accident.
    rm -rf "${WORK}/state" 2>/dev/null || true

    dc rm -sf connector >/dev/null 2>&1 || true
    UAT_CONNECTOR="$connector" UAT_SCHEMAS_FILE="$schemas" \
        dc up -d connector >/dev/null 2>&1 || { bad "${name}: connector would not start"; return 0; }

    # Give the watcher time to attach before the file appears, so the case
    # tests the watch path rather than a race the connector cannot win.
    sleep 2
    cp "${HERE}/fixtures/${fixture}" "${DROP}/"
    # Touch it: a copy onto a watched directory can land as a single create
    # event on some filesystems and the connectors key off modify.
    sleep 1; touch "${DROP}/${fixture}"

    sleep "$SETTLE"

    local accepted rejected logs crashed
    accepted="$(num "$(hec_stat accepted_events)")"
    rejected="$(num "$(hec_stat rejected_batches)")"
    logs="${WORK}/${name}.log"
    podman logs connector-uat-subject >"$logs" 2>&1 || true

    # A traceback is a finding in its own right, whatever the counts say.
    crashed="$(grep -c 'Traceback (most recent call last)' "$logs" || true)"
    crashed="$(num "$crashed")"

    say "  events accepted=${accepted}  batches rejected=${rejected}  tracebacks=${crashed}"

    if [[ "$crashed" -gt 0 ]]; then
        bad "${name}: connector raised" "$(grep -m1 -A2 'Traceback' "$logs" | tr '\n' ' ' | cut -c1-160)"
    else
        ok "${name}: no traceback"
    fi

    if [[ "$accepted" -eq "$(num "$expect")" ]]; then
        ok "${name}: delivered ${accepted}/${expect} events"
    else
        bad "${name}: delivered ${accepted}, expected ${expect}" \
            "$(sed -n '1,6p' "$logs" | tr '\n' ' ' | cut -c1-200)"
    fi

    # Counting arrivals says nothing about whether the right values arrived
    # under the right names, which is the failure that survives a green count.
    if [[ "$accepted" -gt 0 ]]; then
        if python3 "${HERE}/check_delivery.py" "${WORK}/hec-events.jsonl" "$name"; then
            ok "${name}: delivered content is correct"
        else
            bad "${name}: delivered content is wrong" "see the checks above"
        fi
    fi

    # The payload-format check is only meaningful once something was actually
    # posted. With nothing sent, a zero count of code-6 rejections says the
    # connector never ran, not that its payload was well formed.
    local arr
    arr="$(num "$(hec_code_count 6)")"
    if [[ "$arr" -gt 0 ]]; then
        bad "${name}: HEC rejected the payload format ${arr}x (code 6)" \
            "a JSON array body or a non-numeric time field - the whole batch is lost"
    elif [[ "$accepted" -eq 0 && "$rejected" -eq 0 ]]; then
        skip "${name}: payload format not exercised (nothing was posted)"
    else
        ok "${name}: payload format accepted by HEC"
    fi
}

CASES="${1:-all}"

# Guarded with `|| true`: under set -e a `want X && run_case ...` whose guard
# is false makes the whole list return non-zero and kills the run.
maybe() {  # maybe <name> <connector> <schemas> <fixture> <expected>
    if [[ "$CASES" == "all" || "$CASES" == "$1" ]]; then
        run_case "$@" || true
    fi
}

# Expected counts are every row in the fixture, matched and unmatched alike.
# A record no schema claims is still a record: forwarding it under
# <format>:unmatched keeps it searchable, where dropping it makes an empty
# dashboard indistinguishable from a quiet estate.
maybe csv-generic \
    /src/csv/python/csv_splunk_connector.py \
    /src/csv/python/schemas.yaml \
    generic_network.csv 5

maybe csv-trellix \
    /src/csv/python/csv_splunk_connector.py \
    /uat/schemas/trellix.yaml \
    trellix_events.csv 6

maybe json-generic \
    /src/json/python/json_splunk_connector.py \
    /src/json/python/schemas.yaml \
    generic_events.json 5

maybe xml-generic \
    /src/xml/python/xml_splunk_connector.py \
    /src/xml/python/schemas.yaml \
    generic_events.xml 5

if [[ "$CASES" == "all" || "$CASES" == "csv-semicolon" ]]; then
    UAT_CSV_DELIMITER=';' run_case csv-semicolon \
        /src/csv/python/csv_splunk_connector.py \
        /src/csv/python/schemas.yaml \
        semicolon.csv 5 || true
fi

# ------------------------------------------------------------- resume case ---
# The offset contract: a restart re-reads nothing already acknowledged and
# skips nothing that was not. Sniffing a delimiter or re-finding a header
# mid-file both break this, and neither shows up in a single-shot case.
if [[ "$CASES" == "all" || "$CASES" == "csv-resume" ]]; then
    head2 "case: csv-resume"
    hec_reset
    rm -f "${DROP}"/* 2>/dev/null || true
    rm -rf "${WORK}/state" 2>/dev/null || true

    dc rm -sf connector >/dev/null 2>&1 || true
    UAT_CONNECTOR=/src/csv/python/csv_splunk_connector.py \
        UAT_SCHEMAS_FILE=/uat/schemas/trellix.yaml \
        dc up -d connector >/dev/null 2>&1 || true
    sleep 2
    cp "${HERE}/fixtures/trellix_events.csv" "${DROP}/"
    sleep "$SETTLE"

    first="$(num "$(hec_stat accepted_events)")"
    say "  first pass delivered ${first}"

    # Stop, append two more rows, restart. The appended rows are the only
    # thing the second pass may deliver.
    dc rm -sf connector >/dev/null 2>&1 || true
    python3 - "$DROP/trellix_events.csv" <<'PY'
import sys
path = sys.argv[1]
with open(path, "rb") as handle:
    data = handle.read()
header = data.split(b"\r\n", 1)[0].decode()
width = len(header.split(","))
rows = b"".join(
    (",".join([str(900 + i), "2026-09-09T10:00:0%d.000Z" % i] + [""] * (width - 2))
     + "\r\n").encode()
    for i in range(2)
)
with open(path, "ab") as handle:
    handle.write(rows)
print(f"appended 2 rows of {width} columns")
PY
    UAT_CONNECTOR=/src/csv/python/csv_splunk_connector.py \
        UAT_SCHEMAS_FILE=/uat/schemas/trellix.yaml \
        dc up -d connector >/dev/null 2>&1 || true
    sleep "$SETTLE"

    total="$(num "$(hec_stat accepted_events)")"
    delta=$((total - first))
    podman logs connector-uat-subject >"${WORK}/csv-resume.log" 2>&1 || true

    if [[ "$first" -eq 6 ]]; then
        ok "csv-resume: first pass delivered all 6 rows"
    else
        bad "csv-resume: first pass delivered ${first}, expected 6"
    fi
    if [[ "$delta" -eq 2 ]]; then
        ok "csv-resume: restart delivered only the 2 appended rows"
    else
        bad "csv-resume: restart delivered ${delta} rows, expected 2" \
            "more means the offset was lost and events were re-sent; fewer means rows were skipped"
    fi
fi

# ------------------------------------------------------- sql and parquet ---
# Neither needs a server: SQLite is in the standard library and Parquet is a
# file. There is no reason for these two to be the untested pair.

# db_case <name> <connector> <schemas> <extra env assignments...>
db_case() {
    local name="$1" connector="$2" schemas="$3"; shift 3

    head2 "case: ${name}"
    hec_reset
    rm -rf "${WORK}/state" 2>/dev/null || true

    dc rm -sf connector >/dev/null 2>&1 || true
    # Exported, not prefixed: env(1) cannot invoke dc(), which is a function.
    local assignment
    for assignment in "$@"; do export "${assignment?}"; done
    export UAT_CONNECTOR="$connector" UAT_SCHEMAS_FILE="$schemas"
    dc up -d connector >"${WORK}/${name}-up.log" 2>&1 \
        || { bad "${name}: connector would not start" "$(tail -3 "${WORK}/${name}-up.log" | tr '\n' ' ')"; return 0; }

    sleep "$SETTLE"

    local accepted crashed logs
    accepted="$(num "$(hec_stat accepted_events)")"
    logs="${WORK}/${name}.log"
    podman logs connector-uat-subject >"$logs" 2>&1 || true
    crashed="$(num "$(grep -c 'Traceback (most recent call last)' "$logs" || true)")"

    say "  events accepted=${accepted}  tracebacks=${crashed}"

    if [[ "$crashed" -gt 0 ]]; then
        bad "${name}: connector raised" "$(grep -m1 -A3 'Traceback' "$logs" | tr '\n' ' ' | cut -c1-200)"
    else
        ok "${name}: no traceback"
    fi
    if [[ "$accepted" -eq 6 ]]; then
        ok "${name}: delivered 6/6 rows"
    else
        bad "${name}: delivered ${accepted}, expected 6" \
            "$(sed -n '1,8p' "$logs" | tr '\n' ' ' | cut -c1-240)"
    fi
    if [[ "$accepted" -gt 0 ]]; then
        if python3 "${HERE}/check_delivery.py" "${WORK}/hec-events.jsonl" "$name"; then
            ok "${name}: delivered content is correct"
        else
            bad "${name}: delivered content is wrong"
        fi
    fi

    # The cursor contract: a restart with no new rows must deliver nothing.
    dc rm -sf connector >/dev/null 2>&1 || true
    local before="$accepted"
    dc up -d connector >/dev/null 2>&1 || true
    sleep "$SETTLE"
    local after delta
    after="$(num "$(hec_stat accepted_events)")"
    delta=$((after - before))
    if [[ "$delta" -eq 0 ]]; then
        ok "${name}: restart re-sent nothing (cursor persisted)"
    else
        bad "${name}: restart re-sent ${delta} rows" \
            "the cursor did not persist, so every restart duplicates the source"
    fi
}

# Both fixtures are written inside the harness: pyarrow lives there, and the
# repository is mounted read-only, which SQLite cannot use because it opens
# its database read-write even to run a SELECT.
if [[ "$CASES" == "all" || "$CASES" == "sql-trellix" || "$CASES" == "parquet-trellix" ]]; then
    head2 "database fixtures"
    if podman exec -e FIXTURE_DIR=/work/fixtures connector-uat-hec \
            python3 /uat/make_db_fixtures.py; then
        ok "sqlite and parquet fixtures written"
    else
        bad "database fixtures could not be written"
    fi
fi

if [[ "$CASES" == "all" || "$CASES" == "sql-trellix" ]]; then
    db_case sql-trellix \
        /src/sql/python/sql_splunk_connector.py \
        /uat/schemas/trellix-sql.yaml \
        UAT_DB_TYPE=sqlite UAT_DB_CONN_STR=/work/fixtures/epo_events.db
fi

if [[ "$CASES" == "all" || "$CASES" == "parquet-trellix" ]]; then
    db_case parquet-trellix \
        /src/parquet/python/parquet_splunk_connector.py \
        /uat/schemas/trellix-parquet.yaml \
        UAT_PARQUET_DIR=/work/fixtures
fi

# ------------------------------------------------------------------ report ---
head2 "result"
say "passed ${PASS}  failed ${FAIL}  skipped ${SKIP}"
if [[ "$FAIL" -gt 0 ]]; then
    say ""
    say "failures:"
    for f in "${FAILURES[@]}"; do say "  - $f"; done
    exit 1
fi
say "ACCEPTANCE PASSED"
