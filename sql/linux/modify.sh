#!/bin/bash
##########################################################################################
#
# modify.sh: Modifies running SQL Server 2025 config via bash
# Author: Robert Weber
# Usage: ./modify.sh -s localhost -u sa -p YourStrong!Passw0rd -c /path/to/config.ini [-i]
#
##########################################################################################

while getopts s:u:p:c:i opt; do
  case $opt in
    s) server_instance="$OPTARG" ;;
    u) username="$OPTARG" ;;
    p) password="$OPTARG" ;;
    c) config_path="$OPTARG" ;;
    i) use_integrated=true ;;
    *) echo "Usage: $0 -s server -u user -p pass -c config.ini [-i]"; exit 1 ;;
  esac
done

server_instance="${server_instance:-localhost}"
username="${username:-sa}"
config_path="${config_path:-/config.ini}"

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
if [ -f "$config_path" ]; then
  parse_ini "$config_path"
fi

# Connection (integrated not fully supported in Linux bash; use SQL auth primarily)
if [ -z "$use_integrated" ]; then
  if [ -z "$password" ]; then
    echo "Password required if not using integrated security"
    exit 1
  fi
  conn_flags="-S $server_instance -U $username -P $password"
else
  conn_flags="-S $server_instance -E"  # Integrated (if host supports, e.g., Windows or Kerberos setup)
fi

# Memory calc (system-wide or container-aware)
mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2 / 1024}')
max_memory=$(awk "BEGIN {print int($mem_total * $Memory_MaxMemoryPercent)}")
min_memory=$(awk "BEGIN {print int($mem_total * $Memory_MinMemoryPercent)}")

# Define sp_configure query as heredoc
spConfigQuery=$(cat <<EOF
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
EOF
)

# Apply sp_configure
sqlcmd $conn_flags -Q "$spConfigQuery" || echo "Failed to apply sp_configure settings"

# Network changes: For container, suggest docker exec mssql-conf; here assume local or manual
if [ "$Network_TcpPort" != "1433" ]; then
  echo "To change TCP port, exec into container: docker exec -it sql2025 /opt/mssql/bin/mssql-conf set network.tcpport $Network_TcpPort"
  echo "Then restart container"
fi

# Query Store on model
queryStoreQuery=$(cat <<EOF
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
EOF
)
sqlcmd $conn_flags -Q "$queryStoreQuery" || echo "Failed to enable Query Store"

# Model DB settings
modelQuery=$(cat <<EOF
ALTER DATABASE model SET RECOVERY $Database_ModelRecoveryModel;
ALTER DATABASE model SET PAGE_VERIFY $Database_ModelPageVerify;
ALTER DATABASE model SET COMPATIBILITY_LEVEL = $Database_ModelCompatibilityLevel;
ALTER DATABASE model SET AUTO_CREATE_STATISTICS $Database_ModelAutoCreateStatistics;
ALTER DATABASE model SET AUTO_UPDATE_STATISTICS $Database_ModelAutoUpdateStatistics;
ALTER DATABASE model SET PARAMETERIZATION $Database_ModelParameterization;
EOF
)
if [ "$Advanced_EnableOptimizedLocking" = true ]; then
  modelQuery+="ALTER DATABASE model SET OPTIMIZED_LOCKING ON;"
fi
sqlcmd $conn_flags -Q "$modelQuery" || echo "Failed to apply model DB settings"

# Advanced settings
if [ "$Advanced_EnableServerAudit" -eq 1 ]; then
  auditQuery=$(cat <<EOF
IF NOT EXISTS (SELECT * FROM sys.server_audits WHERE name = 'BasicAudit')
CREATE SERVER AUDIT BasicAudit TO FILE (FILEPATH = '/var/opt/mssql/log/');
ALTER SERVER AUDIT BasicAudit WITH (STATE = ON);
EOF
  )
  sqlcmd $conn_flags -Q "$auditQuery" || echo "Failed to enable server audit"
fi
if [ -n "$Advanced_TraceFlags" ]; then
  for flag in $(echo "$Advanced_TraceFlags" | tr ',' ' '); do
    sqlcmd $conn_flags -Q "DBCC TRACEON($flag, -1);" || echo "Failed to set trace flag $flag"
  done
fi
sqlcmd $conn_flags -Q "EXEC sp_configure 'default language', (SELECT langid FROM sys.syslanguages WHERE name = '$Advanced_DefaultLanguage'); RECONFIGURE;" || echo "Failed to set default language"

# Optimize TempDB
cpu_count=$(nproc)
num_temp_files=$(($TempDB_MaxTempFiles < $cpu_count ? $TempDB_MaxTempFiles : $cpu_count))
current_count=$(sqlcmd $conn_flags -Q "SELECT COUNT(*) AS count FROM sys.master_files WHERE database_id=2 AND type=0;" -h -1 | tr -d ' ')
if [ "$current_count" -lt "$num_temp_files" ]; then
  for ((i=current_count+1; i<=num_temp_files; i++)); do
    file_name="tempdb_$i.ndf"
    tempdbQuery=$(cat <<EOF
ALTER DATABASE tempdb
ADD FILE (NAME = '$file_name', FILENAME = '/var/opt/mssql/data/$file_name', SIZE = ${TempDB_TempFileSizeMb}MB, FILEGROWTH = ${TempDB_TempFileGrowthMb}MB);
EOF
    )
    sqlcmd $conn_flags -Q "$tempdbQuery" || echo "Failed to add TempDB file $file_name"
  done
fi

# User Configuration
if [ -n "$Users_UserConfigs" ]; then
  if [ -n "$Users_DefaultDbName" ]; then
    sqlcmd $conn_flags -Q "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '$Users_DefaultDbName') CREATE DATABASE [$Users_DefaultDbName];" || echo "Failed to create default DB"
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

    sqlcmd $conn_flags -Q "IF NOT EXISTS (SELECT name FROM sys.sql_logins WHERE name = '$login_name') CREATE LOGIN [$login_name] WITH PASSWORD = '$password';" || echo "Failed to create login $login_name"

    for role in $server_roles; do
      sqlcmd $conn_flags -Q "ALTER SERVER ROLE [$role] ADD MEMBER [$login_name];" || echo "Failed to add server role $role to $login_name"
    done

    db="${Users_DefaultDbName:-master}"
    for db_role in $db_roles; do
      role_parts=($(echo "$db_role" | tr '@' ' '))
      role_name="${role_parts[0]}"
      role_db="${role_parts[1]:-$db}"
      dbRoleQuery="USE [$role_db]; IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = '$login_name') CREATE USER [$login_name] FOR LOGIN [$login_name]; ALTER ROLE [$role_name] ADD MEMBER [$login_name];"
      sqlcmd $conn_flags -Q "$dbRoleQuery" || echo "Failed to add DB role $role_name in $role_db to $login_name"
    done

    for perm in $permissions; do
      perm_parts=($(echo "$perm" | tr '@' ' '))
      perm_stmt="${perm_parts[0]}"
      perm_db="${perm_parts[1]:-$db}"
      permQuery="USE [$perm_db]; GRANT $perm_stmt TO [$login_name];"
      sqlcmd $conn_flags -Q "$permQuery" || echo "Failed to grant permission $perm_stmt in $perm_db to $login_name"
    done
  done
fi

echo "SQL Server configuration modifications applied successfully."