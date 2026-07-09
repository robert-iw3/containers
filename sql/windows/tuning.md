## SQL Container Tuning

Based on best practices from Microsoft documentation and community discussions, running SQL Server in a container (whether Linux or Windows-based) requires tuning to match the constrained environment. Containers introduce isolation, so optimizations focus on resource alignment, memory management, TempDB contention reduction, and query performance to avoid overhead like OOM kills or throttling. Note that SQL Server in Windows containers has limited official support since 2021 (Linux is preferred for production), but the principles below apply broadly.

I'll provide a baseline configuration assuming SQL Server 2025 (or 2022+) in a container with moderate resources (e.g., 4-8 CPUs, 8-16 GB memory). This is enterprise-grade, drawing from your earlier script setup. Adjust based on workload (OLTP vs OLAP) and test with tools like Query Store or sys.dm_os_wait_stats.

### Key Recommendations Before Configuring
- **Resource Allocation**: Always set container limits to prevent host contention. For Docker:
  - `--cpus=4 --memory=8g` (or in docker-compose: `cpus: '4' memory: 8G`).
  - For Linux containers: Use `--shm-size=1g` to increase shared memory (default 64 MB is too low for SQL). Also, add to `mssql.conf`: `[memory] enablecontainersharedmemory = true`.
  - SQL 2025 auto-detects cgroup v2 limits for better isolation.
- **Storage**: Use volumes for data persistence (e.g., `-v sql-data:/var/opt/mssql`). For performance, mount to fast host storage (SSD/NVMe) and enable Instant File Initialization (grant SE_MANAGE_VOLUME_NAME to SQL service account).
- **General Tips**:
  - Containers can be 2-10x slower than native for I/O-heavy workloads due to filesystem overhead. Run privileged mode (`--privileged`) if needed, but test security implications.
  - Monitor with SQL Server tools: Enable Query Store, default trace, and check waits (e.g., PAGEIOLATCH for I/O issues).
  - For Linux hosts: Disable Transparent Huge Pages (THP) with `echo never > /sys/kernel/mm/transparent_hugepage/enabled`, and set C-States to C1 for low latency. Use TuneD profile `mssql` on RHEL for kernel tweaks.

### Baseline SQL Server Settings
Use `sp_configure` for server-wide options. Set these after install via script or SSMS. Here's a good starting point for a container with 4 CPUs and 8 GB memory:

| Category | Setting | Recommended Value | Rationale |
|----------|---------|-------------------|-----------|
| **Memory** | max server memory (MB) | 6144 (75-80% of container limit, e.g., 80% of 8 GB) | Prevents SQL from consuming all container memory, leaving room for OS/container overhead. Auto-detects limits in 2025. |
| **Memory** | min server memory (MB) | 1024 (10-20% of max) | Ensures stable allocation under load. |
| **Parallelism** | max degree of parallelism | 0 (auto) or 4 (match CPUs if <=8) | Balances parallelism without overwhelming limited CPUs. For OLTP, set to 1 if high contention. |
| **Parallelism** | cost threshold for parallelism | 50 | Reduces unnecessary parallel plans for simple queries. |
| **Optimization** | optimize for ad hoc workloads | 1 (enabled) | Saves plan cache for one-time queries in variable container workloads. |
| **Backup** | backup compression default | 1 (enabled) | Reduces I/O at minor CPU cost; good for container storage limits. |
| **Index** | fill factor (%) | 80 | Reduces fragmentation in write-heavy apps. |
| **Network** | network packet size (B) | 8192 | Improves efficiency for large data transfers over container networks. |
| **Advanced** | blocked process threshold (s) | 5 | Early deadlock detection in constrained env. |
| **Advanced** | cursor threshold | -1 (default) | Dynamic cursors for variable loads. |
| **Advanced** | lightweight pooling | 0 (disabled) | Avoid fiber mode; threads are better in containers. |
| **Advanced** | max worker threads | 0 (auto) | Let SQL calculate based on CPUs (container limits may not be detected pre-2025). |
| **Advanced** | priority boost | 0 (disabled) | Not recommended in modern/container setups. |
| **Advanced** | remote query timeout (s) | 600 | Default; adjust if distributed queries. |
| **Advanced** | user connections | 0 (auto) | Unlimited unless resource-constrained. |
| **Trace** | default trace enabled | 1 | Basic auditing. |

Enable advanced options first: `EXEC sp_configure 'show advanced options', 1; RECONFIGURE;`.

### Database-Level Settings (Apply to Model DB for New Databases)
- Recovery model: FULL (for enterprise point-in-time recovery).
- Page verify: CHECKSUM (data integrity).
- Compatibility level: 170 (SQL 2025 features).
- Auto create/update statistics: ON.
- Parameterization: SIMPLE (default).
- Query Store: ON with AUTO capture, 1000 MB max size, 30-day cleanup, 60-min interval.
- Optimized Locking (2025+): ON (reduces blocking).

### TempDB Optimization
- Add files: Up to 8, matching CPUs (e.g., 4 files for 4 CPUs). Size: 1024 MB initial, 512 MB growth.
- Why: Reduces PAGELATCH contention in containers with limited I/O.

### User/Service Settings
- Run SQL service as a domain account if joined (for security); otherwise, NT Authority\System.
- Enable TCP (port 1433) and Named Pipes.
- Mixed auth for flexibility; strong SA password.
- Create app-specific logins with least privilege (e.g., db_owner for app DB).

### Sample Config Script Snippet
Use a startup script like this to apply at container start:

```powershell
# Memory calc (80% max, 20% min)
$mem = (Get-WmiObject Win32_PhysicalMemory).Capacity / 1MB
$maxMemory = [math]::Round($mem * 0.8)
$minMemory = [math]::Round($mem * 0.2)

# sp_configure
Invoke-Sqlcmd -Query @"
EXEC sp_configure 'show advanced options', 1; RECONFIGURE;
EXEC sp_configure 'max server memory (MB)', $maxMemory; RECONFIGURE;
-- Add other settings here...
"@

# TempDB: Add up to 8 files
$cpuCount = (Get-WmiObject Win32_Processor).NumberOfLogicalProcessors
$numFiles = [math]::Min(8, $cpuCount)
-- Query to add files if needed...
```