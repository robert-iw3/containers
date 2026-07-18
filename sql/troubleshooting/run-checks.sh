#!/bin/sh
# Load and run the DBA troubleshooting procedures against a SQL Server shard.
#
#   ./run-checks.sh <container> <sa-password> [database]
#   ./run-checks.sh sql-stack-shard1 "$SQL_SA_PASSWORD" AppDb
#
# Installs sp_DBA_HealthCheck + sp_DBA_MonitorSP into the target database and
# runs the health check. Read-only against the workload (READ UNCOMMITTED,
# TOP-limited DMV queries). Auto-detects docker vs podman.
set -eu

CTR="${1:?usage: run-checks.sh <container> <sa-password> [database]}"
PW="${2:?sa password required}"
DB="${3:-AppDb}"

if command -v docker >/dev/null 2>&1; then CE=docker
elif command -v podman >/dev/null 2>&1; then CE=podman
else echo "no docker/podman on PATH" >&2; exit 1; fi

DIR="$(cd "$(dirname "$0")" && pwd)"
SQLCMD="/opt/mssql-tools18/bin/sqlcmd -C -S 127.0.0.1 -U sa -P $PW -d $DB -b"

echo "== installing procedures into $CTR:$DB =="
for f in healthcheck.sql stored_proc_monitoring.sql; do
    $CE cp "$DIR/$f" "$CTR:/tmp/$f"
    # shellcheck disable=SC2086
    $CE exec "$CTR" $SQLCMD -i "/tmp/$f"
    echo "   installed $f"
done

echo ""
echo "== running sp_DBA_HealthCheck =="
# shellcheck disable=SC2086
$CE exec "$CTR" $SQLCMD -Q "EXEC dbo.sp_DBA_HealthCheck @LogToTable=0, @ShowFixQueries=1;"

echo ""
echo "Tip: monitor a specific procedure's resource impact with:"
echo "  $CE exec $CTR $SQLCMD -Q \"EXEC dbo.sp_DBA_MonitorSP @ProcedureName='dbo.YourProc', @Execute=1;\""
