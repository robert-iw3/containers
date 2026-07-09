<#
.SYNOPSIS
    Modifies an existing SQL Server 2025 configuration using parameters from script defaults or config.ini.
    Applies enterprise-grade performance, network, service, query store, database, advanced, tempdb, and user settings to a running instance.
    - Connects to a specified SQL Server instance
    - Calculates memory based on system resources (or container if applicable)
    - Optimizes TempDB with multiple files if needed
    - Configures sp_configure options comprehensively
    - Sets model database properties
    - Enables features like Query Store and Optimized Locking
    - Creates or updates users, roles, and permissions
    - Handles service account changes (requires WMI access)
    - Includes robust error handling with try-catch and logging

.DESCRIPTION
    This script can be run on a host or in a container to modify a running SQL Server instance.
    Supports overrides via a specified config.ini file or script defaults.
    Assumes mixed authentication; uses provided credentials to connect.
    Network protocol changes and service restarts are applied if needed (may cause brief downtime).
    For TempDB changes, adds files but does not remove existing ones.
    Use cautiously in production as some changes require service restarts.

.PARAMETER ServerInstance
    SQL Server instance name (e.g., "localhost" or "SERVER\INSTANCENAME"). Default: "localhost"

.PARAMETER Username
    SQL login username for connection (e.g., "sa"). Default: "sa"

.PARAMETER Password
    SQL login password. Required if not using integrated security.

.PARAMETER ConfigPath
    Path to config.ini file. Default: "C:\config.ini"

.PARAMETER UseIntegratedSecurity
    Use Windows integrated security (SSPI) for connection instead of SQL auth. Default: $false

.EXAMPLE
    .\ModifySqlConfig.ps1 -ServerInstance "localhost" -Username "sa" -Password "YourStrong!Passw0rd" -ConfigPath "C:\config.ini"
    .\ModifySqlConfig.ps1 -ServerInstance "localhost" -UseIntegratedSecurity $true

.NOTES
    Requires SqlServer PowerShell module (Install-Module SqlServer if needed).
    For service account changes, run with admin privileges.
    Domain service accounts need appropriate setup.
    UserConfigs format: Comma-separated users, each with semicolon-separated fields (login;pass;serverRoles;dbRoles@db;perms@db).
    Changes to model DB affect new databases only.
    Author: Robert Weber
#>

param (
    [string]$ServerInstance = "localhost",
    [string]$Username = "sa",
    [string]$Password,
    [string]$ConfigPath = "C:\config.ini",
    [bool]$UseIntegratedSecurity = $false
)

# Configurable parameters (defaults)

# [Performance]
$MaxDop = 0
$CostThresholdForParallelism = 50
$OptimizeForAdHocWorkloads = 1
$BackupCompressionDefault = 1
$FillFactorPercent = 80
$NetworkPacketSizeBytes = 8192
$AffinityMask = 0
$AffinityIOMask = 0
$BlockedProcessThresholdSeconds = 5
$CursorThreshold = -1
$LightweightPooling = 0
$MaxWorkerThreads = 0
$PriorityBoost = 0
$RemoteQueryTimeoutSeconds = 600
$UserConnections = 0

# [Memory]
$MaxMemoryPercent = 0.8
$MinMemoryPercent = 0.2

# [Network]
$EnableTcp = $true
$EnableNamedPipes = $true
$TcpPort = 1433

# [Services]
$SqlServiceAccount = "NT Authority\System"
$SqlServicePassword = ""
$AgentServiceAccount = "NT Authority\System"
$AgentServicePassword = ""

# [QueryStore]
$QueryStoreOperationMode = "READ_WRITE"
$QueryStoreCleanupPolicyDays = 30
$QueryStoreDataFlushIntervalSeconds = 900
$QueryStoreMaxStorageSizeMb = 1000
$QueryStoreIntervalLengthMinutes = 60
$QueryStoreSizeBasedCleanupMode = "AUTO"
$QueryStoreQueryCaptureMode = "AUTO"
$QueryStoreWaitStatsCaptureMode = "ON"

# [Database]
$ModelRecoveryModel = "FULL"
$ModelPageVerify = "CHECKSUM"
$ModelCompatibilityLevel = 170  # SQL Server 2025
$ModelAutoCreateStatistics = "ON"
$ModelAutoUpdateStatistics = "ON"
$ModelParameterization = "SIMPLE"

# [Advanced]
$DefaultTraceEnabled = 1
$RemoteAccess = 1
$EnableOptimizedLocking = $true
$EnableServerAudit = 0  # 1 to enable basic server audit
$TraceFlags = ""  # Comma-separated, e.g., "1118,2371" for global trace flags
$DefaultLanguage = "us_english"

# [TempDB]
$MaxTempFiles = 8
$TempFileSizeMb = 1024
$TempFileGrowthMb = 512

# [Users]
$DefaultDbName = ""
$UserConfigs = ""  # e.g., "appuser;AppPass123;bulkadmin;db_owner@MyAppDb;SELECT ON dbo.Table1@MyAppDb,appreader;ReadPass;;db_datareader@MyAppDb;"

# Function to parse config.ini with sections
function Parse-IniFile {
    param ([string]$FilePath)
    $ini = @{}
    $section = ""
    Get-Content $FilePath | ForEach-Object {
        $line = $_.Trim()
        if ($line -match "^\[(.+)\]$") {
            $section = $matches[1].Trim()
            $ini[$section] = @{}
        } elseif ($line -match "^(.+?)\s*=\s*(.+)$") {
            if ($section) {
                $ini[$section][$matches[1].Trim()] = $matches[2].Trim()
            }
        }
    }
    return $ini
}

# Load overrides from config.ini if exists
if (Test-Path $ConfigPath) {
    try {
        $config = Parse-IniFile $ConfigPath
        # Map to variables by section
        if ($config['Performance']) {
            if ($config['Performance']['MaxDop']) { $MaxDop = [int]$config['Performance']['MaxDop'] }
            if ($config['Performance']['CostThresholdForParallelism']) { $CostThresholdForParallelism = [int]$config['Performance']['CostThresholdForParallelism'] }
            if ($config['Performance']['OptimizeForAdHocWorkloads']) { $OptimizeForAdHocWorkloads = [int]$config['Performance']['OptimizeForAdHocWorkloads'] }
            if ($config['Performance']['BackupCompressionDefault']) { $BackupCompressionDefault = [int]$config['Performance']['BackupCompressionDefault'] }
            if ($config['Performance']['FillFactorPercent']) { $FillFactorPercent = [int]$config['Performance']['FillFactorPercent'] }
            if ($config['Performance']['NetworkPacketSizeBytes']) { $NetworkPacketSizeBytes = [int]$config['Performance']['NetworkPacketSizeBytes'] }
            if ($config['Performance']['AffinityMask']) { $AffinityMask = [int]$config['Performance']['AffinityMask'] }
            if ($config['Performance']['AffinityIOMask']) { $AffinityIOMask = [int]$config['Performance']['AffinityIOMask'] }
            if ($config['Performance']['BlockedProcessThresholdSeconds']) { $BlockedProcessThresholdSeconds = [int]$config['Performance']['BlockedProcessThresholdSeconds'] }
            if ($config['Performance']['CursorThreshold']) { $CursorThreshold = [int]$config['Performance']['CursorThreshold'] }
            if ($config['Performance']['LightweightPooling']) { $LightweightPooling = [int]$config['Performance']['LightweightPooling'] }
            if ($config['Performance']['MaxWorkerThreads']) { $MaxWorkerThreads = [int]$config['Performance']['MaxWorkerThreads'] }
            if ($config['Performance']['PriorityBoost']) { $PriorityBoost = [int]$config['Performance']['PriorityBoost'] }
            if ($config['Performance']['RemoteQueryTimeoutSeconds']) { $RemoteQueryTimeoutSeconds = [int]$config['Performance']['RemoteQueryTimeoutSeconds'] }
            if ($config['Performance']['UserConnections']) { $UserConnections = [int]$config['Performance']['UserConnections'] }
        }
        if ($config['Memory']) {
            if ($config['Memory']['MaxMemoryPercent']) { $MaxMemoryPercent = [double]$config['Memory']['MaxMemoryPercent'] }
            if ($config['Memory']['MinMemoryPercent']) { $MinMemoryPercent = [double]$config['Memory']['MinMemoryPercent'] }
        }
        if ($config['Network']) {
            if ($config['Network']['EnableTcp']) { $EnableTcp = [bool]$config['Network']['EnableTcp'] }
            if ($config['Network']['EnableNamedPipes']) { $EnableNamedPipes = [bool]$config['Network']['EnableNamedPipes'] }
            if ($config['Network']['TcpPort']) { $TcpPort = [int]$config['Network']['TcpPort'] }
        }
        if ($config['Services']) {
            if ($config['Services']['SqlServiceAccount']) { $SqlServiceAccount = $config['Services']['SqlServiceAccount'] }
            if ($config['Services']['SqlServicePassword']) { $SqlServicePassword = $config['Services']['SqlServicePassword'] }
            if ($config['Services']['AgentServiceAccount']) { $AgentServiceAccount = $config['Services']['AgentServiceAccount'] }
            if ($config['Services']['AgentServicePassword']) { $AgentServicePassword = $config['Services']['AgentServicePassword'] }
        }
        if ($config['QueryStore']) {
            if ($config['QueryStore']['OperationMode']) { $QueryStoreOperationMode = $config['QueryStore']['OperationMode'] }
            if ($config['QueryStore']['CleanupPolicyDays']) { $QueryStoreCleanupPolicyDays = [int]$config['QueryStore']['CleanupPolicyDays'] }
            if ($config['QueryStore']['DataFlushIntervalSeconds']) { $QueryStoreDataFlushIntervalSeconds = [int]$config['QueryStore']['DataFlushIntervalSeconds'] }
            if ($config['QueryStore']['MaxStorageSizeMb']) { $QueryStoreMaxStorageSizeMb = [int]$config['QueryStore']['MaxStorageSizeMb'] }
            if ($config['QueryStore']['IntervalLengthMinutes']) { $QueryStoreIntervalLengthMinutes = [int]$config['QueryStore']['IntervalLengthMinutes'] }
            if ($config['QueryStore']['SizeBasedCleanupMode']) { $QueryStoreSizeBasedCleanupMode = $config['QueryStore']['SizeBasedCleanupMode'] }
            if ($config['QueryStore']['QueryCaptureMode']) { $QueryStoreQueryCaptureMode = $config['QueryStore']['QueryCaptureMode'] }
            if ($config['QueryStore']['WaitStatsCaptureMode']) { $QueryStoreWaitStatsCaptureMode = $config['QueryStore']['WaitStatsCaptureMode'] }
        }
        if ($config['Database']) {
            if ($config['Database']['ModelRecoveryModel']) { $ModelRecoveryModel = $config['Database']['ModelRecoveryModel'] }
            if ($config['Database']['ModelPageVerify']) { $ModelPageVerify = $config['Database']['ModelPageVerify'] }
            if ($config['Database']['ModelCompatibilityLevel']) { $ModelCompatibilityLevel = [int]$config['Database']['ModelCompatibilityLevel'] }
            if ($config['Database']['ModelAutoCreateStatistics']) { $ModelAutoCreateStatistics = $config['Database']['ModelAutoCreateStatistics'] }
            if ($config['Database']['ModelAutoUpdateStatistics']) { $ModelAutoUpdateStatistics = $config['Database']['ModelAutoUpdateStatistics'] }
            if ($config['Database']['ModelParameterization']) { $ModelParameterization = $config['Database']['ModelParameterization'] }
        }
        if ($config['Advanced']) {
            if ($config['Advanced']['DefaultTraceEnabled']) { $DefaultTraceEnabled = [int]$config['Advanced']['DefaultTraceEnabled'] }
            if ($config['Advanced']['RemoteAccess']) { $RemoteAccess = [int]$config['Advanced']['RemoteAccess'] }
            if ($config['Advanced']['EnableOptimizedLocking']) { $EnableOptimizedLocking = [bool]$config['Advanced']['EnableOptimizedLocking'] }
            if ($config['Advanced']['EnableServerAudit']) { $EnableServerAudit = [int]$config['Advanced']['EnableServerAudit'] }
            if ($config['Advanced']['TraceFlags']) { $TraceFlags = $config['Advanced']['TraceFlags'] }
            if ($config['Advanced']['DefaultLanguage']) { $DefaultLanguage = $config['Advanced']['DefaultLanguage'] }
        }
        if ($config['TempDB']) {
            if ($config['TempDB']['MaxTempFiles']) { $MaxTempFiles = [int]$config['TempDB']['MaxTempFiles'] }
            if ($config['TempDB']['TempFileSizeMb']) { $TempFileSizeMb = [int]$config['TempDB']['TempFileSizeMb'] }
            if ($config['TempDB']['TempFileGrowthMb']) { $TempFileGrowthMb = [int]$config['TempDB']['TempFileGrowthMb'] }
        }
        if ($config['Users']) {
            if ($config['Users']['DefaultDbName']) { $DefaultDbName = $config['Users']['DefaultDbName'] }
            if ($config['Users']['UserConfigs']) { $UserConfigs = $config['Users']['UserConfigs'] }
        }
    } catch {
        Write-Error "Failed to parse config.ini: $_"
    }
} else {
    Write-Host "No config.ini found at $ConfigPath; using script defaults."
}

# Import SqlServer module
try {
    Import-Module SqlServer -ErrorAction Stop
} catch {
    Write-Error "SqlServer module import failed: $_ (Install-Module SqlServer if needed)"
    exit 1
}

# Build connection params for Invoke-Sqlcmd
$connParams = @{
    ServerInstance = $ServerInstance
    ErrorAction = 'Stop'
}
if ($UseIntegratedSecurity) {
    $connParams['IntegratedSecurity'] = $true
} else {
    if (-not $Password) {
        Write-Error "Password required if not using integrated security"
        exit 1
    }
    $connParams['Username'] = $Username
    $connParams['Password'] = $Password
}

# Calculate memory
try {
    $mem = (Get-WmiObject -Class Win32_PhysicalMemory).Capacity / 1MB
    $maxMemory = [math]::Round($mem * $MaxMemoryPercent)
    $minMemory = [math]::Round($mem * $MinMemoryPercent)
} catch {
    Write-Error "Failed to calculate memory settings: $_"
    $maxMemory = 4096  # Fallback
    $minMemory = 1024
}

# Apply sp_configure settings
try {
    $spConfigQuery = @"
EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;
EXEC sp_configure 'max degree of parallelism', $MaxDop;
EXEC sp_configure 'max server memory (MB)', $maxMemory;
EXEC sp_configure 'min server memory (MB)', $minMemory;
EXEC sp_configure 'cost threshold for parallelism', $CostThresholdForParallelism;
EXEC sp_configure 'optimize for ad hoc workloads', $OptimizeForAdHocWorkloads;
EXEC sp_configure 'backup compression default', $BackupCompressionDefault;
EXEC sp_configure 'fill factor (%)', $FillFactorPercent;
EXEC sp_configure 'network packet size (B)', $NetworkPacketSizeBytes;
EXEC sp_configure 'affinity mask', $AffinityMask;
EXEC sp_configure 'affinity I/O mask', $AffinityIOMask;
EXEC sp_configure 'blocked process threshold (s)', $BlockedProcessThresholdSeconds;
EXEC sp_configure 'cursor threshold', $CursorThreshold;
EXEC sp_configure 'default trace enabled', $DefaultTraceEnabled;
EXEC sp_configure 'lightweight pooling', $LightweightPooling;
EXEC sp_configure 'max worker threads', $MaxWorkerThreads;
EXEC sp_configure 'priority boost', $PriorityBoost;
EXEC sp_configure 'remote access', $RemoteAccess;
EXEC sp_configure 'remote query timeout (s)', $RemoteQueryTimeoutSeconds;
EXEC sp_configure 'user connections', $UserConnections;
RECONFIGURE;
"@
    Invoke-Sqlcmd @connParams -Query $spConfigQuery
} catch {
    Write-Error "Failed to apply sp_configure settings: $_"
}

# Configure Network Protocols (requires SqlServer module)
if (Get-Command Set-SqlNetworkConfiguration -ErrorAction SilentlyContinue) {
    try {
        Set-SqlNetworkConfiguration -ProtocolName tcp -InstanceName MSSQLSERVER -Enabled $EnableTcp -TcpPort $TcpPort -ErrorAction Stop
        Set-SqlNetworkConfiguration -ProtocolName np -InstanceName MSSQLSERVER -Enabled $EnableNamedPipes -ErrorAction Stop
        # Restart SQL service (adjust if instance is named)
        Restart-Service -Name MSSQLSERVER -Force
        if ($AgentServiceAccount -ne "NT Authority\System") {
            Restart-Service -Name SQLSERVERAGENT -Force
        }
    } catch {
        Write-Error "Failed to configure network protocols or restart services: $_"
    }
} else {
    Write-Host "SqlServer module not available for network config"
}

# Change Service Accounts (requires local WMI access; for remote, adjust ManagedComputer)
if ($SqlServiceAccount -ne "NT Authority\System" -or $AgentServiceAccount -ne "NT Authority\System") {
    try {
        $mc = New-Object Microsoft.SqlServer.Management.Smo.Wmi.ManagedComputer localhost  # Change 'localhost' for remote
        $sqlService = $mc.Services | Where-Object { $_.Name -eq 'MSSQLSERVER' }
        $sqlService.SetServiceAccount($SqlServiceAccount, $SqlServicePassword)
        $agentService = $mc.Services | Where-Object { $_.Name -eq 'SQLSERVERAGENT' }
        $agentService.SetServiceAccount($AgentServiceAccount, $AgentServicePassword)
        Restart-Service -Name SQLSERVERAGENT -Force
        Restart-Service -Name MSSQLSERVER -Force
    } catch {
        Write-Error "Failed to change service accounts: $_ (ensure admin privileges and domain setup)"
    }
}

# Enable Query Store on model
try {
    Invoke-Sqlcmd @connParams -Query @"
ALTER DATABASE model SET QUERY_STORE = ON (
    OPERATION_MODE = '$QueryStoreOperationMode',
    CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = $QueryStoreCleanupPolicyDays),
    DATA_FLUSH_INTERVAL_SECONDS = $QueryStoreDataFlushIntervalSeconds,
    MAX_STORAGE_SIZE_MB = $QueryStoreMaxStorageSizeMb,
    INTERVAL_LENGTH_MINUTES = $QueryStoreIntervalLengthMinutes,
    SIZE_BASED_CLEANUP_MODE = '$QueryStoreSizeBasedCleanupMode',
    QUERY_CAPTURE_MODE = '$QueryStoreQueryCaptureMode',
    WAIT_STATS_CAPTURE_MODE = '$QueryStoreWaitStatsCaptureMode'
);
"@
} catch {
    Write-Error "Failed to enable Query Store: $_"
}

# Model DB settings
try {
    $modelQuery = @"
ALTER DATABASE model SET RECOVERY $ModelRecoveryModel;
ALTER DATABASE model SET PAGE_VERIFY $ModelPageVerify;
ALTER DATABASE model SET COMPATIBILITY_LEVEL = $ModelCompatibilityLevel;
ALTER DATABASE model SET AUTO_CREATE_STATISTICS $ModelAutoCreateStatistics;
ALTER DATABASE model SET AUTO_UPDATE_STATISTICS $ModelAutoUpdateStatistics;
ALTER DATABASE model SET PARAMETERIZATION $ModelParameterization;
"@
    if ($EnableOptimizedLocking) { $modelQuery += "ALTER DATABASE model SET OPTIMIZED_LOCKING ON;" }
    Invoke-Sqlcmd @connParams -Query $modelQuery
} catch {
    Write-Error "Failed to apply model DB settings: $_"
}

# Advanced settings
try {
    if ($EnableServerAudit -eq 1) {
        Invoke-Sqlcmd @connParams -Query @"
IF NOT EXISTS (SELECT * FROM sys.server_audits WHERE name = 'BasicAudit')
CREATE SERVER AUDIT BasicAudit TO FILE (FILEPATH = 'C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQL\Log\');
ALTER SERVER AUDIT BasicAudit WITH (STATE = ON);
"@
    }
    if ($TraceFlags) {
        $flags = $TraceFlags -split ","
        foreach ($flag in $flags) {
            Invoke-Sqlcmd @connParams -Query "DBCC TRACEON($flag, -1);"
        }
    }
    Invoke-Sqlcmd @connParams -Query "EXEC sp_configure 'default language', (SELECT langid FROM sys.syslanguages WHERE name = '$DefaultLanguage'); RECONFIGURE;"
} catch {
    Write-Error "Failed to apply advanced settings: $_"
}

# Optimize TempDB
try {
    $cpuCount = (Get-WmiObject Win32_Processor).NumberOfLogicalProcessors
    $numTempFiles = [math]::Min($MaxTempFiles, $cpuCount)
    $currentTempFiles = Invoke-Sqlcmd @connParams -Query "SELECT COUNT(*) AS count FROM sys.master_files WHERE database_id=2 AND type=0;"
    $currentCount = $currentTempFiles.count

    if ($currentCount -lt $numTempFiles) {
        for ($i = $currentCount + 1; $i -le $numTempFiles; $i++) {
            $fileName = "tempdb_$i.ndf"
            Invoke-Sqlcmd @connParams -Query @"
ALTER DATABASE tempdb
ADD FILE (NAME = '$fileName', FILENAME = 'C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQL\DATA\$fileName', SIZE = $($TempFileSizeMb)MB, FILEGROWTH = $($TempFileGrowthMb)MB);
"@
        }
    }
} catch {
    Write-Error "Failed to optimize TempDB: $_"
}

# User Configuration
if ($UserConfigs) {
    try {
        if ($DefaultDbName) {
            Invoke-Sqlcmd @connParams -Query "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '$DefaultDbName') CREATE DATABASE [$DefaultDbName];"
        }
        $users = $UserConfigs -split ","
        foreach ($user in $users) {
            $parts = $user -split ";"
            if ($parts.Count -lt 2) { continue }
            $loginName = $parts[0]
            $password = $parts[1]
            $serverRoles = if ($parts.Count -ge 3) { $parts[2] -split "," } else { @() }
            $dbRoles = if ($parts.Count -ge 4) { $parts[3] -split "," } else { @() }
            $permissions = if ($parts.Count -ge 5) { $parts[4] -split "," } else { @() }

            Invoke-Sqlcmd @connParams -Query "IF NOT EXISTS (SELECT name FROM sys.sql_logins WHERE name = '$loginName') CREATE LOGIN [$loginName] WITH PASSWORD = '$password';"

            foreach ($role in $serverRoles) {
                Invoke-Sqlcmd @connParams -Query "ALTER SERVER ROLE [$role] ADD MEMBER [$loginName];"
            }

            $db = if ($DefaultDbName) { $DefaultDbName } else { "master" }
            foreach ($dbRole in $dbRoles) {
                $roleParts = $dbRole -split "@"
                $roleName = $roleParts[0]
                $roleDb = if ($roleParts.Count -gt 1) { $roleParts[1] } else { $db }
                Invoke-Sqlcmd @connParams -Query "USE [$roleDb]; IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = '$loginName') CREATE USER [$loginName] FOR LOGIN [$loginName]; ALTER ROLE [$roleName] ADD MEMBER [$loginName];"
            }

            foreach ($perm in $permissions) {
                $permParts = $perm -split "@"
                $permStmt = $permParts[0]
                $permDb = if ($permParts.Count -gt 1) { $permParts[1] } else { $db }
                Invoke-Sqlcmd @connParams -Query "USE [$permDb]; GRANT $permStmt TO [$loginName];"
            }
        }
    } catch {
        Write-Error "Failed to configure users: $_"
    }
}

Write-Host "SQL Server configuration modifications applied successfully."