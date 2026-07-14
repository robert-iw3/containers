#!/usr/bin/env bash
# Apply the SIEM ISM policies and data-stream index templates to a running
# OpenSearch cluster. Requires: OPENSEARCH_URL, OPENSEARCH_USER, OPENSEARCH_PASSWORD.
set -euo pipefail

URL="${OPENSEARCH_URL:-https://localhost:9200}"
USER="${OPENSEARCH_USER:-admin}"
PASS="${OPENSEARCH_PASSWORD:-${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_PASSWORD}}"
HERE="$(cd "$(dirname "$0")" && pwd)"

python3 "${HERE}/gen_ism.py" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for name, policy in data["policies"].items():
    print("policy\t" + name.replace(".", "-") + "-ism\t" + json.dumps(policy))
for name, tmpl in data["templates"].items():
    print("template\t" + name.replace(".", "-") + "-template\t" + json.dumps(tmpl))
' | while IFS=$'\t' read -r kind id body; do
    if [ "$kind" = "policy" ]; then
        path="_plugins/_ism/policies/${id}"
    else
        path="_index_template/${id}"
    fi
    echo "Applying ${kind} ${id}"
    curl -ksS -u "${USER}:${PASS}" -H 'Content-Type: application/json' \
        -X PUT "${URL}/${path}" -d "${body}" >/dev/null
done

echo "SIEM ISM policies and templates applied."
