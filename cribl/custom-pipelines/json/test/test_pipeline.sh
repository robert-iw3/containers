#!/bin/bash
# Verify the json pipeline exists on the leader (group-scoped, variant-suffixed).
set -euo pipefail

INI_FILE="../config/config.ini"

parse_ini() {
  local section="$1" key="$2"
  awk -F "=" '/^\['"$section"'\]/{a=1;next}/^\[/{a=0} a {k=$1; gsub(/ /,"",k); if (k=="'"$key"'") {v=$2; gsub(/ /,"",v); print v}}' "$INI_FILE"
}

CRIBL_HOST=$(parse_ini "cribl" "host")
CRIBL_USER=$(parse_ini "cribl" "user")
CRIBL_PASS=$(parse_ini "cribl" "pass")
PIPELINE_ID=$(parse_ini "json" "pipeline_id")
PIPELINE_GROUP=$(parse_ini "json" "pipeline_group")
PIPELINE_GROUP=${PIPELINE_GROUP:-default}
PIPELINE_VARIANT=$(parse_ini "json" "pipeline_variant")
PIPELINE_VARIANT=${PIPELINE_VARIANT:-logs}
PIPELINE_ID_VARIANT="${PIPELINE_ID}_${PIPELINE_VARIANT}"

TOKEN=$(curl -s -X POST "$CRIBL_HOST/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CRIBL_USER\",\"password\":\"$CRIBL_PASS\"}" \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
if [ -z "$TOKEN" ]; then echo "ERROR: Cribl API login failed for $CRIBL_USER"; exit 1; fi
AUTH_HEADER="Authorization: Bearer $TOKEN"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
  "$CRIBL_HOST/api/v1/m/$PIPELINE_GROUP/pipelines/$PIPELINE_ID_VARIANT")
if [ "$STATUS" = "200" ]; then
  echo "Pipeline $PIPELINE_ID_VARIANT exists"
else
  echo "Pipeline $PIPELINE_ID_VARIANT not found (HTTP $STATUS)"
  exit 1
fi
