#!/bin/bash
# Verify the terraform-provisioned connection and collector exist on the leader.
set -euo pipefail

INI_FILE="../config/config.ini"

parse_ini() {
  local section="$1" key="$2"
  awk -F "=" '/^\['"$section"'\]/{a=1;next}/^\[/{a=0} a {k=$1; gsub(/ /,"",k); if (k=="'"$key"'") {v=$2; gsub(/ /,"",v); print v}}' "$INI_FILE"
}

CRIBL_HOST=$(parse_ini "cribl" "host")
CRIBL_USER=$(parse_ini "cribl" "user")
CRIBL_PASS=$(parse_ini "cribl" "pass")
PIPELINE_GROUP=$(parse_ini "sql" "pipeline_group")
PIPELINE_GROUP=${PIPELINE_GROUP:-default}
CONN_ID="mssql_connection"
COLLECTOR_ID="mssql_collector"

TOKEN=$(curl -s -X POST "$CRIBL_HOST/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CRIBL_USER\",\"password\":\"$CRIBL_PASS\"}" \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
if [ -z "$TOKEN" ]; then echo "ERROR: Cribl API login failed for $CRIBL_USER"; exit 1; fi
AUTH_HEADER="Authorization: Bearer $TOKEN"

check_resource() { # check_resource <path> <label>
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/$1")
  if [ "$status" = "200" ]; then
    echo "$2 exists."
  else
    echo "Error: $2 missing (HTTP $status)"
    exit 1
  fi
}

check_resource "m/$PIPELINE_GROUP/lib/database-connections/$CONN_ID" "Connection $CONN_ID"
check_resource "m/$PIPELINE_GROUP/lib/jobs/$COLLECTOR_ID" "Collector $COLLECTOR_ID"
