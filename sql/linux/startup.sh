#!/bin/bash
#######################################################################
#
# startup.sh: Configures SQL Server 2025 in Linux container at startup
# Author: Robert Weber
#
#######################################################################
# Defaults (sections match config.ini)
# [Performance]
Performance_MaxDop=0
Performance_CostThresholdForParallelism=50
Performance_OptimizeForAdHocWorkloads=1
Performance_BackupCompressionDefault=1
Performance_FillFactorPercent=80
Performance_NetworkPacketSizeBytes=8192
Performance_AffinityMask=0
Performance_AffinityIOMask=0
Performance_BlockedProcessThresholdSeconds=5
Performance_CursorThreshold=-1
Performance_LightweightPooling=0
Performance_MaxWorkerThreads=0
Performance_PriorityBoost=0
Performance_RemoteQueryTimeoutSeconds=600
Performance_UserConnections=0

# [Memory]
Memory_MaxMemoryPercent=0.8
Memory_MinMemoryPercent=0.2

# [Network]
Network_EnableTcp=true
Network_TcpPort=1433

# [QueryStore]
QueryStore_OperationMode="READ_WRITE"
QueryStore_CleanupPolicyDays=30
QueryStore_DataFlushIntervalSeconds=900
QueryStore_MaxStorageSizeMb=1000
QueryStore_IntervalLengthMinutes=60
QueryStore_SizeBasedCleanupMode="AUTO"
QueryStore_QueryCaptureMode="AUTO"
QueryStore_WaitStatsCaptureMode="ON"

# [Database]
Database_ModelRecoveryModel="FULL"
Database_ModelPageVerify="CHECKSUM"
Database_ModelCompatibilityLevel=170
Database_ModelAutoCreateStatistics="ON"
Database_ModelAutoUpdateStatistics="ON"
Database_ModelParameterization="SIMPLE"

# [Advanced]
Advanced_DefaultTraceEnabled=1
Advanced_RemoteAccess=1
Advanced_EnableOptimizedLocking=true
Advanced_EnableServerAudit=0
Advanced_TraceFlags=""
Advanced_DefaultLanguage="us_english"

# [TempDB]
TempDB_MaxTempFiles=8
TempDB_TempFileSizeMb=1024
TempDB_TempFileGrowthMb=512

# [Users]
Users_DefaultDbName=""
Users_UserConfigs=""

# Function to parse config.ini
parse_ini() {
  local file="$1"
  local section=""
  while IFS= read -r line; do
    line="${line%%;*}"; line="${line%%#*}"  # Strip comments
    line="${line// /}"  # Remove spaces
    if [[ $line =~ ^\[(.*)\]$ ]]; then
      section="${BASH_REMATCH[1]}"
    elif [[ $line =~ ^(.*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      eval "${section}_${key}=\"${value}\""
    fi
  done < "$file"
}

# Load config.ini if exists
if [ -f "/config.ini" ]; then
  parse_ini "/config.ini"
fi

# Required env
if [ -z "$MSSQL_SA_PASSWORD" ]; then
  echo "MSSQL_SA_PASSWORD required"
  exit 1
fi
sa_password="$MSSQL_SA_PASSWORD"

# Start SQL Server in background
/opt/mssql/bin/sqlservr &

# Wait for startup
sleep 30s  # Adjust if needed

# Calculate memory (use cgroup for 2025)
mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2 / 1024}')
max_memory=$(awk "BEGIN {print int($mem_total * $Memory_MaxMemoryPercent)}")
min_memory=$(awk "BEGIN {print int($mem_total * $Memory_MinMemoryPercent)}")

# Apply sp_configure
sqlcmd -S localhost -U sa -P "$sa_password" -Q "
EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;
EXEC sp_configure 'max degree of parallelism', $Performance_MaxDop;
EXEC sp_configure 'max server memory (MB)', $max_memory;
EXEC sp_configure 'min server memory (MB)', $min_memory;
EXEC sp_configure 'cost threshold for parallelism', $Performance_CostThresholdForParallelism;
EXEC sp_configure 'optimize for ad hoc workloads', $Performance_OptimizeForAdHocWorkloads;
EXEC sp_configure 'backup compression default', $Performance_BackupCompressionDefault;
EXEC sp_configure 'fill factor (%)', $Performance_FillFactorPercent;
EXEC sp_configure 'network packet size (B)', $Performance_NetworkPacketSizeBytes;
EXEC sp_configure 'affinity mask', $Performance_AffinityMask;
EXEC sp_configure 'affinity I/O mask', $Performance_AffinityIOMask;
EXEC sp_configure 'blocked process threshold (s)', $Performance_BlockedProcessThresholdSeconds;
EXEC sp_configure 'cursor threshold', $Performance_CursorThreshold;
EXEC sp_configure 'default trace enabled', $Advanced_DefaultTraceEnabled;
EXEC sp_configure 'lightweight pooling', $Performance_LightweightPooling;
EXEC sp_configure 'max worker threads', $Performance_MaxWorkerThreads;
EXEC sp_configure 'priority boost', $Performance_PriorityBoost;
EXEC sp_configure 'remote access', $Advanced_RemoteAccess;
EXEC sp_configure 'remote query timeout (s)', $Performance_RemoteQueryTimeoutSeconds;
EXEC sp_configure 'user connections', $Performance_UserConnections;
RECONFIGURE;
"

# Network (use mssql-conf)
if [ "$Network_TcpPort" != "1433" ]; then
  /opt/mssql/bin/mssql-conf set network.tcpport "$Network_TcpPort"
  kill $(pidof sqlservr); sleep 5s; /opt/mssql/bin/sqlservr &
  sleep 10s
fi

# Query Store on model
sqlcmd -S localhost -U sa -P "$sa_password" -Q "
ALTER DATABASE model SET QUERY_STORE = ON (
    OPERATION_MODE = '$QueryStore_OperationMode',
    CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = $QueryStore_CleanupPolicyDays),
    DATA_FLUSH_INTERVAL_SECONDS = $QueryStore_DataFlushIntervalSeconds,
    MAX_STORAGE_SIZE_MB = $QueryStore_MaxStorageSizeMb,
    INTERVAL_LENGTH_MINUTES = $QueryStore_IntervalLengthMinutes,
    SIZE_BASED_CLEANUP_MODE = '$QueryStore_SizeBasedCleanupMode',
    QUERY_CAPTURE_MODE = '$QueryStore_QueryCaptureMode',
    WAIT_STATS_CAPTURE_MODE = '$QueryStore_WaitStatsCaptureMode'
);
"

# Model DB
sqlcmd -S localhost -U sa -P "$sa_password" -Q "
ALTER DATABASE model SET RECOVERY $Database_ModelRecoveryModel;
ALTER DATABASE model SET PAGE_VERIFY $Database_ModelPageVerify;
ALTER DATABASE model SET COMPATIBILITY_LEVEL = $Database_ModelCompatibilityLevel;
ALTER DATABASE model SET AUTO_CREATE_STATISTICS $Database_ModelAutoCreateStatistics;
ALTER DATABASE model SET AUTO_UPDATE_STATISTICS $Database_ModelAutoUpdateStatistics;
ALTER DATABASE model SET PARAMETERIZATION $Database_ModelParameterization;
$(if [ "$Advanced_EnableOptimizedLocking" = true ]; then echo "ALTER DATABASE model SET OPTIMIZED_LOCKING ON;"; fi)
"

# Advanced
if [ "$Advanced_EnableServerAudit" -eq 1 ]; then
  sqlcmd -S localhost -U sa -P "$sa_password" -Q "
IF NOT EXISTS (SELECT * FROM sys.server_audits WHERE name = 'BasicAudit')
CREATE SERVER AUDIT BasicAudit TO FILE (FILEPATH = '/var/opt/mssql/log/');
ALTER SERVER AUDIT BasicAudit WITH (STATE = ON);
"
fi
if [ -n "$Advanced_TraceFlags" ]; then
  for flag in $(echo "$Advanced_TraceFlags" | tr ',' ' '); do
    sqlcmd -S localhost -U sa -P "$sa_password" -Q "DBCC TRACEON($flag, -1);"
  done
fi
sqlcmd -S localhost -U sa -P "$sa_password" -Q "EXEC sp_configure 'default language', (SELECT langid FROM sys.syslanguages WHERE name = '$Advanced_DefaultLanguage'); RECONFIGURE;"

# TempDB
cpu_count=$(nproc)
num_temp_files=$(($TempDB_MaxTempFiles < $cpu_count ? $TempDB_MaxTempFiles : $cpu_count))
current_count=$(sqlcmd -S localhost -U sa -P "$sa_password" -Q "SELECT COUNT(*) AS count FROM sys.master_files WHERE database_id=2 AND type=0;" -h -1 | tr -d ' ')
if [ "$current_count" -lt "$num_temp_files" ]; then
  for ((i=current_count+1; i<=num_temp_files; i++)); do
    file_name="tempdb_$i.ndf"
    sqlcmd -S localhost -U sa -P "$sa_password" -Q "
    ALTER DATABASE tempdb
    ADD FILE (NAME = '$file_name', FILENAME = '/var/opt/mssql/data/$file_name', SIZE = ${TempDB_TempFileSizeMb}MB, FILEGROWTH = ${TempDB_TempFileGrowthMb}MB);
    "
  done
fi

# User Configuration (SQL logins only)
if [ -n "$Users_UserConfigs" ]; then
  if [ -n "$Users_DefaultDbName" ]; then
    sqlcmd -S localhost -U sa -P "$sa_password" -Q "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '$Users_DefaultDbName') CREATE DATABASE [$Users_DefaultDbName];"
  fi
  IFS=',' read -r -a users <<< "$Users_UserConfigs"
  for user in "${users[@]}"; do
    IFS=';' read -r -a parts <<< "$user"
    if [ ${#parts[@]} -lt 2 ]; then continue; fi
    login_name="${parts[0]}"
    password="${parts[1]}"
    server_roles=$(echo "${parts[2]:-}" | tr ',' ' ')
    db_roles=$(echo "${parts[3]:-}" | tr ',' ' ')
    permissions=$(echo "${parts[4]:-}" | tr ',' ' ')

    sqlcmd -S localhost -U sa -P "$sa_password" -Q "IF NOT EXISTS (SELECT name FROM sys.sql_logins WHERE name = '$login_name') CREATE LOGIN [$login_name] WITH PASSWORD = '$password';"

    for role in $server_roles; do
      sqlcmd -S localhost -U sa -P "$sa_password" -Q "ALTER SERVER ROLE [$role] ADD MEMBER [$login_name];"
    done

    db="${Users_DefaultDbName:-master}"
    for db_role in $db_roles; do
      role_parts=($(echo "$db_role" | tr '@' ' '))
      role_name="${role_parts[0]}"
      role_db="${role_parts[1]:-$db}"
      sqlcmd -S localhost -U sa -P "$sa_password" -Q "USE [$role_db]; IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = '$login_name') CREATE USER [$login_name] FOR LOGIN [$login_name]; ALTER ROLE [$role_name] ADD MEMBER [$login_name];"
    done

    for perm in $permissions; do
      perm_parts=($(echo "$perm" | tr '@' ' '))
      perm_stmt="${perm_parts[0]}"
      perm_db="${perm_parts[1]:-$db}"
      sqlcmd -S localhost -U sa -P "$sa_password" -Q "USE [$perm_db]; GRANT $perm_stmt TO [$login_name];"
    done
  done
fi

# Tail log to keep container running
tail -f /var/opt/mssql/log/errorlog