#!/usr/bin/env bash
# Apply the generated ILM policies + data-stream index templates to Elasticsearch.
#   ES=https://localhost:9200 ELASTIC_PASSWORD=... CA=/path/ca.crt ./apply-siem.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ES="${ES:-https://localhost:9200}"
PW="${ELASTIC_PASSWORD:?set ELASTIC_PASSWORD}"
CURL=(curl -s -u "elastic:${PW}" -H "Content-Type: application/json")
if [ -n "${CA:-}" ]; then CURL+=(--cacert "$CA"); else CURL+=(-k); fi

python3 "$DIR/gen_siem.py" "$DIR/datasets.yml"
for f in "$DIR"/generated/ilm/*.json; do
  n=$(basename "$f" .json); echo "ILM policy: $n"
  "${CURL[@]}" -X PUT "$ES/_ilm/policy/$n" -d @"$f" >/dev/null
done
for f in "$DIR"/generated/templates/*.json; do
  n=$(basename "$f" .json); echo "index template: logs-$n"
  "${CURL[@]}" -X PUT "$ES/_index_template/logs-$n" -d @"$f" >/dev/null
done
echo "SIEM ILM + labeled-index templates applied to $ES"
