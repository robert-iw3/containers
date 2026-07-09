-- =============================================
-- SQL Health Check & Troubleshooting Report (For SQL Server 2022/2025)
-- Covers: Indexing, Missing Indexes, Heaps, Deadlocks, Waits, Plan Cache, Memory, Parameter Sniffing, LOB, Corruption, etc.
-- Author: RW
-- Features: Error handling, low-impact queries (TOP limits, READ UNCOMMITTED), optional logging
-- SET XACT_ABORT ON for immediate abort/rollback on errors; improved corruption check without custom log table; added thresholds for some checks; batched inserts where possible
-- =============================================
CREATE OR ALTER PROCEDURE dbo.sp_DBA_HealthCheck
    @DatabaseName sysname = NULL, -- NULL = Server-wide or all user DBs where applicable
    @LogToTable bit = 1, -- 1 = Write to DBA_HealthLog table
    @ShowFixQueries bit = 1 -- 1 = Include generated fix queries
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;  -- Added: Abort entire transaction on runtime errors for clean rollback
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED; -- Low impact, no locks

    DECLARE @StartTime datetime2 = SYSDATETIME();
    DECLARE @ErrorMessage nvarchar(4000);

    BEGIN TRY
        -- Temp result table
        IF OBJECT_ID('tempdb..#HealthReport') IS NOT NULL DROP TABLE #HealthReport;
        CREATE TABLE #HealthReport (
            ID int IDENTITY(1,1),
            Category nvarchar(80),
            Issue nvarchar(120),
            Severity nvarchar(20), -- Critical, High, Medium, Low
            CurrentStatus nvarchar(400),
            Recommendation nvarchar(800),
            FixQuery nvarchar(MAX)
        );

        -- =============================================
        -- 1. Index Fragmentation & Page Splits (Low impact: LIMITED mode, threshold >10%)
        -- =============================================
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT
            'Indexing',
            'High Index Fragmentation',
            CASE WHEN avg_fragmentation_in_percent > 30 THEN 'Critical'
                 WHEN avg_fragmentation_in_percent > 10 THEN 'High' ELSE 'Medium' END,
            CONCAT(ROUND(avg_fragmentation_in_percent,1), '% fragmentation on ',
                   i.name, ' (', t.name, ')'),
            'Rebuild indexes >30% frag, reorganize 10-30%. Run during maintenance window.',
            'ALTER INDEX [' + i.name + '] ON [' + SCHEMA_NAME(t.schema_id) + '].[' + t.name + '] ' +
            CASE WHEN avg_fragmentation_in_percent > 30 THEN 'REBUILD' ELSE 'REORGANIZE' END + ' WITH (ONLINE = ON);'
        FROM sys.dm_db_index_physical_stats(DB_ID(@DatabaseName), NULL, NULL, NULL, 'LIMITED') ps
        JOIN sys.indexes i ON ps.object_id = i.object_id AND ps.index_id = i.index_id
        JOIN sys.tables t ON ps.object_id = t.object_id
        WHERE avg_fragmentation_in_percent > 10
          AND i.type IN (1,2) -- Clustered + Nonclustered
          AND ps.alloc_unit_type_desc = 'IN_ROW_DATA'
        ORDER BY avg_fragmentation_in_percent DESC;

        -- =============================================
        -- 2. Missing Indexes (Low impact: TOP 10, impact threshold >10)
        -- =============================================
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT TOP 10
            'Indexing',
            'Missing Index Suggestion',
            'High',
            CONCAT('Impact: ', ROUND(avg_total_user_cost * avg_user_impact * user_seeks,0), ' | Equality: ', equality_columns),
            'Evaluate and create index if beneficial. Test impact first.',
            'CREATE NONCLUSTERED INDEX IX_' + REPLACE(NEWID(), '-', '') +
            ' ON ' + statement + ' (' + ISNULL(equality_columns, '') +
            ISNULL(inequality_columns, '') + ') INCLUDE (' + included_columns + ');'
        FROM sys.dm_db_missing_index_groups g
        JOIN sys.dm_db_missing_index_group_stats gs ON g.index_group_handle = gs.group_handle
        JOIN sys.dm_db_missing_index_details d ON g.index_handle = d.index_handle
        WHERE database_id = DB_ID(@DatabaseName) OR @DatabaseName IS NULL
          AND avg_user_impact > 10  -- Added threshold for relevance
        ORDER BY (avg_total_user_cost * avg_user_impact * user_seeks) DESC;

        -- =============================================
        -- 3. Heap Tables (No Clustered Index)
        -- =============================================
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT
            'Storage',
            'Heap Table Detected',
            'High',
            t.name + ' has no clustered index',
            'Add clustered index on primary or selective column. Avoid for staging tables.',
            'CREATE CLUSTERED INDEX CX_' + t.name + ' ON [' + SCHEMA_NAME(t.schema_id) + '].[' + t.name + '] (ID); -- Replace ID with actual column'
        FROM sys.tables t
        LEFT JOIN sys.indexes i ON t.object_id = i.object_id AND i.type = 1
        WHERE i.object_id IS NULL AND t.is_ms_shipped = 0
          AND (@DatabaseName IS NULL OR DB_NAME() = @DatabaseName);

        -- =============================================
        -- 4. Deadlock Detection (Recent from XE or Log; low impact)
        -- =============================================
        -- Assumes deadlock graph XE session running; fallback to error log parse
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT
            'Execution',
            'Recent Deadlocks',
            'Critical',
            CONCAT('Deadlocks in last 24h: ', COUNT(*)),
            'Review deadlock graphs. Optimize queries, add indexes, or use SNAPSHOT isolation.',
            'SELECT * FROM sys.event_log WHERE event_type = ''deadlock''; -- Azure; or check XE'
        FROM sys.dm_os_ring_buffers -- Or use XE query
        WHERE ring_buffer_type = 'RING_BUFFER_DEADLOCK'
          AND timestamp > DATEADD(HOUR, -24, GETDATE())
        GROUP BY ring_buffer_type
        HAVING COUNT(*) > 0;

        -- =============================================
        -- 5. Top Waits (CXPACKET, PAGEIOLATCH, etc.; low impact: TOP 10)
        -- =============================================
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT TOP 10
            'Execution',
            'High Wait Type',
            CASE WHEN wait_type LIKE 'CX%' THEN 'High'
                 WHEN wait_type LIKE 'PAGEIOLATCH%' THEN 'Critical' ELSE 'Medium' END,
            CONCAT(wait_type, ': ', ROUND(wait_time_ms / 1000.0 / 60, 2), ' min total wait'),
            CASE wait_type
                WHEN 'CXPACKET' THEN 'Tune MAXDOP or cost threshold for parallelism.'
                WHEN 'PAGEIOLATCH_XX' THEN 'Improve I/O: SSD, more RAM, or index tuning.'
                ELSE 'Investigate specific wait: Check DMVs or Query Store.'
            END,
            CASE wait_type
                WHEN 'CXPACKET' THEN 'EXEC sp_configure ''max degree of parallelism'', 4; RECONFIGURE;'
                ELSE 'SELECT * FROM sys.dm_os_waiting_tasks WHERE wait_type = ''' + wait_type + ''';'
            END
        FROM sys.dm_os_wait_stats
        WHERE wait_time_ms > 0 AND wait_type NOT LIKE '%SLEEP%'
        ORDER BY wait_time_ms DESC;

        -- =============================================
        -- 6. Plan Cache Bloat (Low impact: Aggregate, threshold >1000)
        -- =============================================
        DECLARE @AdHocEnabled int;
        SELECT @AdHocEnabled = value_in_use FROM sys.configurations WHERE name = 'optimize for ad hoc workloads';
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT
            'Plan Cache',
            'Plan Cache Bloat',
            'High',
            CONCAT('Ad Hoc Plans: ', COUNT(*), ' | Optimize Enabled: ', @AdHocEnabled),
            'Enable optimize for ad hoc if not set. Parameterize queries.',
            'EXEC sp_configure ''optimize for ad hoc workloads'', 1; RECONFIGURE;'
        FROM sys.dm_exec_cached_plans
        WHERE usecounts = 1 AND objtype = 'Adhoc'
        HAVING COUNT(*) > 1000; -- Threshold for bloat

        -- =============================================
        -- 7. Memory Pressure & PAGELATCH (Low impact: Clerks & Waits, threshold >100s)
        -- =============================================
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT
            'Memory',
            'Memory Pressure',
            'Critical',
            CONCAT('PAGELATCH Waits: ', ROUND(wait_time_ms / 1000.0 / 60, 2), ' min | Top Clerk: ', type),
            'Increase max memory, clear cache, or tune queries to reduce buffer churn.',
            'DBCC FREEPROCCACHE; -- Caution: Production impact'
        FROM sys.dm_os_wait_stats ws
        CROSS APPLY (SELECT TOP 1 type FROM sys.dm_os_memory_clerks ORDER BY pages_kb DESC) mc
        WHERE ws.wait_type LIKE 'PAGELATCH%'
          AND wait_time_ms > 100000; -- Threshold 100s

        -- =============================================
        -- 8. Parameter Sniffing Detection (Low impact: Query Store check, variance >10k)
        -- =============================================
        IF EXISTS (SELECT 1 FROM sys.databases WHERE is_query_store_on = 1)
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT TOP 5
            'Optimization',
            'Parameter Sniffing Suspected',
            'High',
            CONCAT('Query ID: ', query_id, ' | Duration Variance: ', ROUND(STDEV(duration_ms),0)),
            'Use OPTIMIZE FOR UNKNOWN or Query Store to force plan.',
            'EXEC sys.sp_query_store_force_plan @query_id = ' + CAST(query_id AS varchar) + ', @plan_id = (SELECT TOP 1 plan_id FROM sys.query_store_plan WHERE query_id = ' + CAST(query_id AS varchar) + ' ORDER BY avg_duration DESC);'
        FROM sys.query_store_runtime_stats
        GROUP BY query_id
        HAVING STDEV(duration_ms) > 10000 -- High variance threshold
        ORDER BY STDEV(duration_ms) DESC;

        -- =============================================
        -- 9. Large Row / LOB Issues (Low impact: Check row sizes >7k bytes)
        -- =============================================
        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        SELECT
            'Storage',
            'Large Rows / LOB Overflow',
            'Medium',
            CONCAT('Table: ', t.name, ' | Max Row Size: ', MAX(row_size)),
            'Redesign table to fit <8060 bytes or use FILESTREAM for LOBs.',
            'SELECT * FROM ' + t.name + ' WHERE DATALENGTH(lob_col) > 8000; -- Investigate large rows'
        FROM sys.tables t
        CROSS APPLY (
            SELECT SUM(max_length) AS row_size FROM sys.columns WHERE object_id = t.object_id
        ) c
        WHERE row_size > 7000 -- Threshold near 8060 byte limit
        GROUP BY t.name;

        -- =============================================
        -- 10. Corruption Check Summary (Optimized: Use DMV for last check time, no custom table)
        -- =============================================
        DECLARE @LastCheckDate datetime;
        SELECT @LastCheckDate = MAX(last_execution_time)
        FROM sys.dm_exec_procedure_stats
        WHERE object_id = OBJECT_ID('sys.dbcc_checkdb');  -- Approximate via stats

        INSERT INTO #HealthReport (Category, Issue, Severity, CurrentStatus, Recommendation, FixQuery)
        VALUES (
            'Storage',
            'Potential Corruption',
            'Critical',
            'Last CHECKDB Approx: ' + ISNULL(CAST(@LastCheckDate AS varchar), 'Unknown'),
            'Run DBCC CHECKDB during maintenance. Restore if errors.',
            'DBCC CHECKDB (''' + ISNULL(@DatabaseName, DB_NAME()) + ''') WITH NO_INFOMSGS;'
        )
        WHERE @LastCheckDate IS NULL OR @LastCheckDate < DATEADD(MONTH, -1, GETDATE()); -- Stale if >1 month

        -- Final Output (batched select)
        SELECT
            Category,
            Issue,
            Severity,
            CurrentStatus,
            Recommendation,
            CASE WHEN @ShowFixQueries = 1 THEN FixQuery ELSE NULL END AS SuggestedFix
        FROM #HealthReport
        ORDER BY
            CASE Severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END,
            Category, Issue;

        -- Log to permanent table (optimized insert)
        IF @LogToTable = 1
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'DBA_HealthLog')
            BEGIN
                CREATE TABLE dbo.DBA_HealthLog (
                    LogID int IDENTITY PRIMARY KEY,
                    RunDate datetime2 DEFAULT SYSDATETIME(),
                    Category nvarchar(80),
                    Issue nvarchar(120),
                    Severity nvarchar(20),
                    CurrentStatus nvarchar(400),
                    Recommendation nvarchar(800)
                );
            END

            INSERT INTO dbo.DBA_HealthLog (Category, Issue, Severity, CurrentStatus, Recommendation)
            SELECT Category, Issue, Severity, CurrentStatus, Recommendation
            FROM #HealthReport;
        END

    END TRY
    BEGIN CATCH
        SELECT @ErrorMessage = ERROR_MESSAGE();
        PRINT 'Error in sp_DBA_HealthCheck: ' + @ErrorMessage;
        -- Optional: Log error to table or file
    END CATCH

    IF OBJECT_ID('tempdb..#HealthReport') IS NOT NULL DROP TABLE #HealthReport;
END
GO