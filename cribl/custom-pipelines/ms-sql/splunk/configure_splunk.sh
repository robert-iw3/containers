#!/bin/bash

INI_FILE="../config/config.ini"
LOG_FILE="splunk_config.log"

log() {
  local level="$1"
  shift
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" | tee -a "$LOG_FILE"
}

parse_ini() {
  local section="$1" key="$2"
  awk -F "=" '/^\['"$section"'\]/{a=1;next}/^\[/{a=0} a && $1=="'"$key"'" {gsub(/ /,"",$2); print $2}' "$INI_FILE"
}

CRIBL_HOST=$(parse_ini "cribl" "host")
CRIBL_USER=$(parse_ini "cribl" "user")
CRIBL_PASS=$(parse_ini "cribl" "pass")
SPLUNK_HEC_URL=$(parse_ini "splunk" "hec_url")
SPLUNK_HEC_TOKEN=$(parse_ini "splunk" "hec_token")
DEST_ID=$(parse_ini "splunk" "destination_id" || echo "splunk_hec_dest")

AUTH_HEADER="Authorization: Basic $(echo -n $CRIBL_USER:$CRIBL_PASS | base64)"

DEST_ENDPOINT="m/local/destinations"

DEST_PAYLOAD='{
  "id": "'"$DEST_ID"'",
  "type": "splunk_hec",
  "description": "Splunk HEC destination",
  "config": {
    "url": "'"$SPLUNK_HEC_URL"'",
    "token": "'"$SPLUNK_HEC_TOKEN"'",
    "ack": true
  }
}'

curl -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  "$CRIBL_HOST/api/v1/$DEST_ENDPOINT" -d "$DEST_PAYLOAD"

log "INFO" "Splunk destination created"