#!/bin/bash

INI_FILE="../config/config.ini"

parse_ini() {
  local section="$1" key="$2"
  awk -F "=" '/^\['"$section"'\]/{a=1;next}/^\[/{a=0} a && $1=="'"$key"'" {gsub(/ /,"",$2); print $2}' "$INI_FILE"
}

CRIBL_HOST=$(parse_ini "cribl" "host")
CRIBL_USER=$(parse_ini "cribl" "user")
CRIBL_PASS=$(parse_ini "cribl" "pass")
PIPELINE_ID=$(parse_ini "xml" "pipeline_id")

AUTH_HEADER="Authorization: Basic $(echo -n $CRIBL_USER:$CRIBL_PASS | base64)"

curl -s -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/pipelines/$PIPELINE_ID" | jq .id

if [ $? -eq 0 ]; then
  echo "Pipeline exists"
else
  echo "Pipeline not found"
fi