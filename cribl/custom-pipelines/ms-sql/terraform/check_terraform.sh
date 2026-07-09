#!/bin/bash

CRIBL_HOST="https://your-cribl-instance.example.com"
CRIBL_USER="admin"
CRIBL_PASS="password"
AUTH_HEADER="Authorization: Basic $(echo -n $CRIBL_USER:$CRIBL_PASS | base64)"
CONN_ID="mssql_conn"
COLLECTOR_ID="mssql_collector"

# Function to check API response
check_response() {
  if [ "$1" -ne 200 ] && [ "$1" -ne 201 ]; then
    echo "Error: API returned status $1"
    exit 1
  fi
}

# Check connection
CONN_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/connections/$CONN_ID")
check_response "$CONN_RESPONSE"
echo "Connection $CONN_ID exists."

# Check collector
COL_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/collectors/$COLLECTOR_ID")
check_response "$COL_RESPONSE"
echo "Collector $COLLECTOR_ID exists."