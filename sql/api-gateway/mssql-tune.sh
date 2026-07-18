#!/bin/bash
# Entrypoint for a tuned SQL Server shard: start the engine, wait for it to
# accept connections, apply mssql-tune.sql once, then hand control back to the
# server process. Writes /tmp/tuned as a readiness marker the healthcheck
# checks, so dependants only see the shard as healthy after tuning is applied.
set -euo pipefail

: "${MSSQL_SA_PASSWORD:?MSSQL_SA_PASSWORD is required}"
MAXDOP="${MSSQL_MAXDOP:-2}"
COST_THRESHOLD="${MSSQL_COST_THRESHOLD:-50}"
MAX_MEMORY_MB="${MSSQL_MAX_MEMORY_MB:-1300}"
TEMPDB_FILES="${MSSQL_TEMPDB_FILES:-4}"

SQLCMD="/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P ${MSSQL_SA_PASSWORD}"

rm -f /tmp/tuned

# Start the engine in the background.
/opt/mssql/bin/sqlservr &
SERVER_PID=$!

# Wait for it to accept connections.
for _ in $(seq 1 60); do
    if $SQLCMD -Q "SELECT 1" -b -o /dev/null 2>/dev/null; then
        break
    fi
    sleep 2
done

echo "--> applying shard tuning (MAXDOP=$MAXDOP cost=$COST_THRESHOLD mem=${MAX_MEMORY_MB}MB tempdb=$TEMPDB_FILES)"
$SQLCMD -b \
    -v MAXDOP="$MAXDOP" \
    -v COST_THRESHOLD="$COST_THRESHOLD" \
    -v MAX_MEMORY_MB="$MAX_MEMORY_MB" \
    -v TEMPDB_FILES="$TEMPDB_FILES" \
    -i /usr/local/bin/mssql-tune.sql
echo "--> tuning applied"
touch /tmp/tuned

# Hand control back to the engine (container lives as long as it does).
wait "$SERVER_PID"
