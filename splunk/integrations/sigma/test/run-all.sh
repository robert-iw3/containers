#!/usr/bin/env bash
# Prove this integration works in your environment, not just in ours.
#
# Install the app, point this at the instance, and it answers the questions
# that decide whether the deployment is trustworthy:
#
#   does every rule convert, parse and fit the schedule the instance allows
#   is the instance configured so detections can actually be written
#   does a planted attack get detected, at four levels of camouflage
#   does clean background produce false positives
#   does every dashboard panel run without error
#
# A detection product that is quiet and a detection product that is broken
# look identical from the outside. The only way to tell them apart is to
# put activity you labelled yourself through it and see what comes back.
#
#   ./test/run-all.sh --container epo-uat-indexer --uf epo-uat-uf
#   ./test/run-all.sh --local --rules ./rules-core/.../process_creation
#   ./test/run-all.sh --container splunk --phases preflight,instance
#
# Exit status is 0 only if every phase passed. Each phase prints its own
# verdict, and a phase that could not run says so rather than passing.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="epo-uat-indexer"
UF="epo-uat-uf"
RULES="$HERE/rules-core/SigmaHQ_sigma/core/rules/windows/process_creation"
LINUX_RULES="$HERE/rules-core/SigmaHQ_sigma/core/rules/linux"
PHASES="preflight,instance,detection,dashboards"
TIERS="t1,t2,t3,t4"
SLOTS=7
COUNT=8
WAIT=600
OUT="$HERE/test/results"
FAILED=0
SUMMARY=()

usage() { sed -n '2,22p' "$0"; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --container) CONTAINER="${2:-}"; shift 2 ;;
        --uf)        UF="${2:-}"; shift 2 ;;
        --local)     CONTAINER=""; UF=""; shift ;;
        --rules)     RULES="${2:-}"; shift 2 ;;
        --linux-rules) LINUX_RULES="${2:-}"; shift 2 ;;
        --phases)    PHASES="${2:-}"; shift 2 ;;
        --tiers)     TIERS="${2:-}"; shift 2 ;;
        --slots)     SLOTS="${2:-}"; shift 2 ;;
        --count)     COUNT="${2:-}"; shift 2 ;;
        --wait)      WAIT="${2:-}"; shift 2 ;;
        --out)       OUT="${2:-}"; shift 2 ;;
        -h|--help)   usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done

mkdir -p "$OUT" "$HERE/test/batches"
export PYTHONPATH="$HERE/pylib:${PYTHONPATH:-}"
has() { case ",$PHASES," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
rule() { printf '\n%s\n  %s\n%s\n' "$(printf '═%.0s' $(seq 1 72))" "$1" "$(printf '═%.0s' $(seq 1 72))"; }
note() { SUMMARY+=("$1"); }

# ── 1. the rule set, offline ────────────────────────────────────────────
if has preflight; then
    rule "1. THE RULE SET — checked without touching Splunk"
    FIELDS=""
    [ -f "$HERE/planning/available-fields.txt" ] && FIELDS="--fields $HERE/planning/available-fields.txt"
    if python3 "$HERE/bin/preflight.py" "$RULES" "$LINUX_RULES" --slots "$SLOTS" $FIELDS; then
        note "preflight            PASS"
    else
        note "preflight            FAIL  the rule set is not safe to deploy"; FAILED=1
    fi
fi

# ── 2. the instance ─────────────────────────────────────────────────────
if has instance; then
    rule "2. THE INSTANCE — can it carry and record detections"
    ARG="--local"; [ -n "$CONTAINER" ] && ARG="--container $CONTAINER"
    if bash "$HERE/bin/check-instance.sh" $ARG; then
        note "instance check       PASS"
    else
        note "instance check       FAIL  detections cannot be written as configured"; FAILED=1
    fi
fi

# ── 3. detection, against activity we labelled ──────────────────────────
if has detection; then
    rule "3. DETECTION — planted activity, and clean background"

    # Control first. It plants nothing, so every detection it produces is a
    # false positive with no ground truth to confuse it. Run it before the
    # tiers so a noisy rule set is visible before recall is measured.
    echo; echo "  ── control: background only, nothing planted ──"
    python3 "$HERE/test/synthesize.py" --rules "$RULES" --count 0 --tier t3 \
        --window-minutes 8 --seed 101 --out "$HERE/test/batches/control.json" 2>&1 | sed -n '2,4p'
    if python3 "$HERE/test/validate-round.py" --batch "$HERE/test/batches/control.json" \
            --container "$CONTAINER" --uf "$UF" --wait "$WAIT" \
            --out "$OUT/control.json" 2>&1 | sed -n '/KPI/,/precision/p;/fired on background/,$p'; then
        FP=$(python3 -c "import json;print(json.load(open('$OUT/control.json'))['unplanted'])" 2>/dev/null || echo "?")
        if [ "$FP" = "0" ]; then
            note "false positives      PASS  0 on clean background"
        else
            note "false positives      WARN  $FP rule(s) fired on background"
        fi
    fi

    IFS=',' read -ra TS <<< "$TIERS"
    for t in "${TS[@]}"; do
        echo; echo "  ── $t ──"
        python3 "$HERE/test/synthesize.py" --rules "$RULES" --count "$COUNT" --tier "$t" \
            --window-minutes 8 --seed 101 --out "$HERE/test/batches/$t.json" 2>&1 | sed -n '2,4p'
        python3 "$HERE/test/validate-round.py" --batch "$HERE/test/batches/$t.json" \
            --container "$CONTAINER" --uf "$UF" --wait "$WAIT" \
            --out "$OUT/$t.json" 2>&1 | sed -n '/KPI/,/precision/p;/MISSED/,/^$/p'
        R=$(python3 -c "import json;print(json.load(open('$OUT/$t.json'))['recall_pct'])" 2>/dev/null || echo 0)
        M=$(python3 -c "import json;print(json.load(open('$OUT/$t.json'))['missed'])" 2>/dev/null || echo "?")
        if [ "${R%%.*}" = "100" ]; then
            note "recall $t             PASS  100%"
        else
            note "recall $t             FAIL  ${R}%, $M rule(s) missed"; FAILED=1
        fi
    done
fi

# ── 4. the dashboards ───────────────────────────────────────────────────
if has dashboards; then
    rule "4. THE DASHBOARDS — every panel search, against live data"
    if python3 "$HERE/test/qa-dashboards.py" --container "$CONTAINER" --wait "$WAIT"; then
        note "dashboard searches   PASS  no panel errored"
    else
        note "dashboard searches   FAIL  a panel shows an error"; FAILED=1
    fi
fi

# ── verdict ─────────────────────────────────────────────────────────────
rule "RESULT"
for line in "${SUMMARY[@]}"; do printf '  %s\n' "$line"; done
echo
if [ "$FAILED" -eq 0 ]; then
    printf '  Every phase passed. Results written to %s\n\n' "$OUT"
else
    printf '  At least one phase failed. Read the detail above before deploying.\n\n'
fi
exit "$FAILED"
