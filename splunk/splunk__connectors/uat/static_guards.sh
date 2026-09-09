#!/usr/bin/env bash
# Guards against defect classes that cost a full debugging session each.
#
#   ./static_guards.sh
#
# Every pattern below is a bug that has shipped in this tree and that no unit
# test reaches, because the code carrying it does not import cleanly. A grep is
# the cheapest thing that catches it.
#
# Files are enumerated with find rather than grep -r: grep here is ugrep, which
# honours .gitignore, so a recursive search silently skips ignored paths and
# reports a clean result for files it never opened.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

sources() {
    find "$ROOT" \
        -type d \( -name work -o -name target -o -name __pycache__ -o -name fixtures \) -prune -o \
        -type f \( -name '*.py' -o -name 'Dockerfile' -o -name '*.Dockerfile' \) -print
}

guard() {  # guard <label> <pattern> <why>
    local label="$1" pattern="$2" why="$3"
    local hits
    hits="$(sources | xargs grep -nE "$pattern" 2>/dev/null || true)"
    if [[ -n "$hits" ]]; then
        printf '  FAIL  %s\n' "$label"
        printf '        %s\n' "$why"
        printf '        %s\n' "$hits" | sed -n '1,6p'
        FAIL=$((FAIL + 1))
    else
        printf '  ok    %s\n' "$label"
    fi
}

echo "static guards"

guard "no JSON array posted to HEC" \
    'session\.post\([^)]*json=(batch|cim_batch|events|envelopes)' \
    "HEC reads objects, not an array; an array body is rejected with code 6 and the whole batch is lost"

guard "no Counter.inc_by" \
    '\.inc_by\(' \
    "prometheus_client Counter exposes inc(amount); inc_by raises AttributeError on the success path"

guard "no multiprocessing.Queue.Empty" \
    'except\s+Queue\.Empty' \
    "multiprocessing.Queue has no Empty attribute; the correct class is queue.Empty"

guard "no get_lock on a Manager dict" \
    'file_positions\.get_lock\(\)' \
    "Manager().dict() has no get_lock; that API belongs to multiprocessing.Value"

guard "no elasticsearch_async" \
    '^\s*(from|import)\s+elasticsearch_async' \
    "unmaintained since Elasticsearch 6 and not installable; use the _bulk API directly"

# Both spellings: a literal FROM, and the ARG indirection that a plain FROM
# check reads straight past.
guard "no end-of-life Python base image" \
    '(^FROM .*|base_image=.*)python:3\.(6|7|8|9|10|11)[.-]' \
    "an unsupported interpreter receives no security fixes"

guard "no unpinned pip install" \
    '^RUN pip install( --no-cache-dir)? [a-z].*[^=]$' \
    "an unpinned install makes the image a different thing on every build"

guard "no lxml huge_tree" \
    'huge_tree\s*=\s*True' \
    "disables libxml2's limits on documents this code did not write"

guard "no lxml entity resolution" \
    'resolve_entities\s*=\s*True' \
    "lets a document pull external references and expand nested entities"

echo
if [[ "$FAIL" -gt 0 ]]; then
    echo "${FAIL} guard(s) tripped"
    exit 1
fi
echo "all guards clear"
