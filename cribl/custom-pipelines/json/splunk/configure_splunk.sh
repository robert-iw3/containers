#!/bin/bash
# Create (idempotently) a Splunk HEC destination on the Cribl leader.
set -euo pipefail

INI_FILE="../config/config.ini"
LOG_FILE="splunk_config.log"

log() {
  local level="$1"
  shift
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" | tee -a "$LOG_FILE"
}

parse_ini() {
  local section="$1" key="$2"
  awk -F "=" '/^\['"$section"'\]/{a=1;next}/^\[/{a=0} a {k=$1; gsub(/ /,"",k); if (k=="'"$key"'") {v=$2; gsub(/ /,"",v); print v}}' "$INI_FILE"
}

CRIBL_HOST=$(parse_ini "cribl" "host")
CRIBL_USER=$(parse_ini "cribl" "user")
CRIBL_PASS=$(parse_ini "cribl" "pass")
PIPELINE_GROUP=$(parse_ini "json" "pipeline_group")
PIPELINE_GROUP=${PIPELINE_GROUP:-default}
SPLUNK_HEC_URL=$(parse_ini "splunk" "hec_url")
SPLUNK_HEC_TOKEN=$(parse_ini "splunk" "hec_token")
DEST_ID=$(parse_ini "splunk" "destination_id")
DEST_ID=${DEST_ID:-splunk_hec_dest}

if [ -z "$CRIBL_HOST" ] || [ -z "$CRIBL_USER" ] || [ -z "$CRIBL_PASS" ]; then
  log "ERROR" "Missing [cribl] keys"
  exit 1
fi

TOKEN=$(curl -s -X POST "$CRIBL_HOST/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CRIBL_USER\",\"password\":\"$CRIBL_PASS\"}" \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
if [ -z "$TOKEN" ]; then log "ERROR" "Cribl API login failed for $CRIBL_USER"; exit 1; fi
AUTH_HEADER="Authorization: Bearer $TOKEN"

DEST_ENDPOINT="m/$PIPELINE_GROUP/system/outputs"

EXISTS=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/$DEST_ENDPOINT/$DEST_ID")
if [ "$EXISTS" = "200" ]; then
  log "INFO" "Destination $DEST_ID exists. Skipping creation."
  exit 0
fi

# Outputs use a flat schema: type-specific keys sit next to id/type.
DEST_PAYLOAD='{
  "id": "'"$DEST_ID"'",
  "type": "splunk_hec",
  "url": "'"$SPLUNK_HEC_URL"'",
  "token": "'"$SPLUNK_HEC_TOKEN"'"
}'

STATUS=$(curl -s -o response.json -w "%{http_code}" -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$CRIBL_HOST/api/v1/$DEST_ENDPOINT" -d "$DEST_PAYLOAD")
if [ "$STATUS" = "200" ] || [ "$STATUS" = "201" ]; then
  log "INFO" "Splunk destination $DEST_ID created"
  rm -f response.json
else
  log "ERROR" "Destination creation failed ($STATUS): $(cat response.json)"
  rm -f response.json
  exit 1
fi
