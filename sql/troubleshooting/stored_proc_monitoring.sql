-- =============================================
-- Stored Procedure Monitor & Benchmark Script
-- Executes a given SP (with optional params), monitors performance impact, logs details, and suggests improvements
-- XACT_ABORT ON, indexing, validation, auto-purge, dynamic XE path, expanded XE parsing (waits/plans), more metrics (logical reads, spills), threshold params, Query Store integration if enabled
-- Low overhead: Snapshots DMVs before/after, no tracing unless specified
-- Author: RW
-- Usage: EXEC dbo.sp_DBA_MonitorSP @ProcedureName = 'dbo.MyProc', @Params = '@ID=1', @Execute = 1, @CPUThreshold = 2000
-- =============================================

CREATE OR ALTER PROCEDURE dbo.sp_DBA_MonitorSP
    @ProcedureName sysname,                 -- e.g., 'dbo.YourStoredProc'
    @Params nvarchar(MAX) = NULL,           -- e.g., '@ID=42, @Name=''Test'''
    @Execute bit = 1,                       -- 1 = Run the SP; 0 = Dry run (monitor only)
    @LogToTable bit = 1,                    -- 1 = Log to DBA_SPMonitorLog
    @EnableTracing bit = 0,                 -- 1 = Use lightweight XE for detailed waits/plans (higher overhead)
    @XEPath nvarchar(256) = N'C:\Temp\DBA_SPTrace.xel',  -- Dynamic path
    @PurgeDays int = 30,                    -- Auto-purge logs older than X days
    @DurationThreshold int = 5000,          -- ms; flag high duration
    @CPUThreshold int = 1000,               -- ms delta; flag high CPU
    @IOThreshold int = 10000                -- ops delta; flag high I/O
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;                      -- Abort on errors for clean rollback
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

    DECLARE @RunID int, @StartTime datetime2 = SYSDATETIME(), @EndTime datetime2,
            @ExecSQL nvarchar(MAX), @ErrorMessage nvarchar(4000),
            @PreCPU bigint, @PostCPU bigint, @PreIO bigint, @PostIO bigint,
            @PreLogicalReads bigint, @PostLogicalReads bigint, @PreSpills int, @PostSpills int,
            @PreWaits xml, @PostWaits xml, @QueryPlan xml,
            @ProcObjectID int, @XEData xml, @XEWaits nvarchar(MAX) = '', @XEPlan xml;

    BEGIN TRY
        -- Validate inputs
        SET @ProcObjectID = OBJECT_ID(@ProcedureName);
        IF @ProcObjectID IS NULL
        BEGIN
            RAISERROR('Procedure %s does not exist.', 16, 1, @ProcedureName);
            RETURN;
        END

        -- Create/update logging table with indexes
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'DBA_SPMonitorLog')
        CREATE TABLE dbo.DBA_SPMonitorLog (
            RunID int IDENTITY PRIMARY KEY,
            RunDate datetime2 DEFAULT SYSDATETIME(),
            ProcedureName sysname,
            Params nvarchar(MAX),
            DurationMs int,
            Status nvarchar(20),  -- Success / Failed
            ErrorMessage nvarchar(4000),
            DeltaCPU bigint,      -- ms
            DeltaIO bigint,       -- operations (reads + writes)
            DeltaLogicalReads bigint,
            DeltaSpills int,
            PreWaitStats xml,
            PostWaitStats xml,
            XEWaitDetails nvarchar(MAX),
            QueryPlan xml,        -- Captured plan
            Recommendations nvarchar(MAX)
        );

        -- Add indexes if missing
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_DBA_SPMonitorLog_RunDate')
            CREATE INDEX IX_DBA_SPMonitorLog_RunDate ON dbo.DBA_SPMonitorLog (RunDate);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_DBA_SPMonitorLog_ProcedureName')
            CREATE INDEX IX_DBA_SPMonitorLog_ProcedureName ON dbo.DBA_SPMonitorLog (ProcedureName);

        -- Auto-purge old logs (optimized with index)
        DELETE FROM dbo.DBA_SPMonitorLog WHERE RunDate < DATEADD(DAY, -@PurgeDays, GETDATE());

        -- Pre-run snapshots (batched into single query where possible)
        SELECT
            @PreCPU = SUM(cpu_time),
            @PreIO = SUM(reads + writes),
            @PreLogicalReads = SUM(logical_reads),
            @PreSpills = SUM(spills)
        FROM sys.dm_exec_requests;

        SELECT @PreWaits = (
            SELECT TOP 10 wait_type, wait_time_ms
            FROM sys.dm_os_wait_stats
            ORDER BY wait_time_ms DESC
            FOR XML RAW('wait'), ROOT('waits')
        );

        -- Optional XE tracing (add spills event, filter by SP)
        IF @EnableTracing = 1
        BEGIN
            IF EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = 'DBA_SPTrace')
                DROP EVENT SESSION DBA_SPTrace ON SERVER;
            CREATE EVENT SESSION DBA_SPTrace ON SERVER
            ADD EVENT sqlserver.sql_statement_completed(
                ACTION(sqlserver.query_plan_hash, sqlserver.sql_text)
                WHERE sql_text LIKE '%' + @ProcedureName + '%'),
            ADD EVENT sqlserver.rpc_completed(
                WHERE sql_text LIKE '%' + @ProcedureName + '%'),
            ADD EVENT sqlserver.spill_to_tempdb
            ADD TARGET package0.event_file(PATH = @XEPath);
            ALTER EVENT SESSION DBA_SPTrace ON SERVER STATE = START;
        END

        -- Execute the SP
        IF @Execute = 1
        BEGIN
            SET @ExecSQL = 'EXEC ' + @ProcedureName + ' ' + ISNULL(@Params, '');
            EXEC sp_executesql @ExecSQL;
        END

        -- Post-run snapshots
        SET @EndTime = SYSDATETIME();

        SELECT
            @PostCPU = SUM(cpu_time),
            @PostIO = SUM(reads + writes),
            @PostLogicalReads = SUM(logical_reads),
            @PostSpills = SUM(spills)
        FROM sys.dm_exec_requests;

        SELECT @PostWaits = (
            SELECT TOP 10 wait_type, wait_time_ms
            FROM sys.dm_os_wait_stats
            ORDER BY wait_time_ms DESC
            FOR XML RAW('wait'), ROOT('waits')
        );

        -- Capture query plan (optimized with filter)
        SELECT TOP 1 @QueryPlan = qp.query_plan
        FROM sys.dm_exec_cached_plans cp
        CROSS APPLY sys.dm_exec_sql_text(cp.plan_handle) st
        CROSS APPLY sys.dm_exec_query_plan(cp.plan_handle) qp
        WHERE st.text LIKE '%' + @ProcedureName + '%'
        ORDER BY cp.usecounts DESC;

        -- Stop and parse XE (expanded: extract waits, plans, spills)
        IF @EnableTracing = 1
        BEGIN
            ALTER EVENT SESSION DBA_SPTrace ON SERVER STATE = STOP;
            SELECT @XEData = CAST(event_data AS xml)
            FROM sys.fn_xe_file_target_read_file(@XEPath + '*', NULL, NULL, NULL);

            -- Parse XE: Waits (aggregate)
            SET @XEWaits = (
                SELECT STRING_AGG(CONCAT(wait_type, ': ', wait_time_ms), '; ')
                FROM (
                    SELECT
                        x.n.value('(data[@name="wait_type"]/value)[1]', 'nvarchar(50)') AS wait_type,
                        SUM(x.n.value('(data[@name="wait_time_ms"]/value)[1]', 'bigint')) AS wait_time_ms
                    FROM @XEData.nodes('//event') AS x(n)
                    GROUP BY x.n.value('(data[@name="wait_type"]/value)[1]', 'nvarchar(50)')
                ) w
            );

            -- Parse XE: Plan (first one)
            SET @XEPlan = (
                SELECT TOP 1 x.n.query('(action[@name="query_plan"]/value)[1]')
                FROM @XEData.nodes('//event') AS x(n)
            );

            -- Parse Spills
            DECLARE @SpillCount int = (SELECT COUNT(*) FROM @XEData.nodes('//event[@name="spill_to_tempdb"]'));

            -- Cleanup XE files (optimize storage)
            DECLARE @CleanupCmd nvarchar(500) = 'DEL ' + @XEPath + '*';
            EXEC master..xp_cmdshell @CleanupCmd;  -- Enable xp_cmdshell if needed (security risk; alternative: manual)
        END

        -- Analyze & recommend (expanded with new metrics/thresholds)
        DECLARE @Recommendations nvarchar(MAX) = '', @DurationMs int = DATEDIFF(MS, @StartTime, @EndTime);
        IF @DurationMs > @DurationThreshold SET @Recommendations += 'High duration: Consider partitioning or async exec. ';
        IF (@PostCPU - @PreCPU) > @CPUThreshold SET @Recommendations += 'High CPU: Optimize loops/joins or use columnstore. ';
        IF (@PostIO - @PreIO) > @IOThreshold SET @Recommendations += 'High I/O: Add filters or covering indexes. ';
        IF (@PostLogicalReads - @PreLogicalReads) > 50000 SET @Recommendations += 'High logical reads: Tune query or increase buffer. ';
        IF @PostSpills > 0 SET @Recommendations += 'TempDB spills detected: Increase sort/hash memory or rewrite query. ';
        IF CHARINDEX('CXPACKET', CAST(@PostWaits AS nvarchar(MAX))) > 0
            SET @Recommendations += 'Parallelism waits: Adjust MAXDOP or cost threshold. ';
        IF CHARINDEX('PAGELATCH', CAST(@PostWaits AS nvarchar(MAX))) > 0
            SET @Recommendations += 'Memory pressure: Increase max memory or evict cache. ';
        IF @XEWaits <> '' SET @Recommendations += 'XE Waits: ' + @XEWaits + '. ';

        -- Query Store integration (if enabled)
        DECLARE @QSRecommendations nvarchar(MAX) = '';
        IF EXISTS (SELECT 1 FROM sys.databases WHERE is_query_store_on = 1)
        BEGIN
            SELECT @QSRecommendations = STRING_AGG(CONCAT('QS Suggestion: Force Plan ID ', plan_id), '; ')
            FROM sys.query_store_plan
            WHERE query_id IN (SELECT query_id FROM sys.query_store_query_text WHERE query_text LIKE '%' + @ProcedureName + '%')
              AND is_forced_plan = 0;  -- Suggest forcing good plans
            IF @QSRecommendations <> '' SET @Recommendations += @QSRecommendations;
        END

        -- Log
        INSERT INTO dbo.DBA_SPMonitorLog (ProcedureName, Params, DurationMs, Status,
                                          DeltaCPU, DeltaIO, DeltaLogicalReads, DeltaSpills,
                                          PreWaitStats, PostWaitStats, XEWaitDetails,
                                          QueryPlan, Recommendations)
        SELECT @ProcedureName, @Params, @DurationMs, 'Success',
               (@PostCPU - @PreCPU), (@PostIO - @PreIO), (@PostLogicalReads - @PreLogicalReads), (@PostSpills - @PreSpills),
               @PreWaits, @PostWaits, @XEWaits,
               @QueryPlan, @Recommendations;

        SET @RunID = SCOPE_IDENTITY();

        PRINT 'SP Monitor Completed. RunID: ' + CAST(@RunID AS varchar) +
              '. Duration: ' + CAST(@DurationMs AS varchar) + ' ms';
        PRINT 'Delta CPU: ' + CAST((@PostCPU - @PreCPU) AS varchar) +
              ' ms | Delta I/O: ' + CAST((@PostIO - @PreIO) AS varchar) + ' ops';
        PRINT 'Delta Logical Reads: ' + CAST((@PostLogicalReads - @PreLogicalReads) AS varchar) +
              ' | Delta Spills: ' + CAST((@PostSpills - @PreSpills) AS varchar);
        PRINT 'Recommendations: ' + @Recommendations;
        SELECT * FROM dbo.DBA_SPMonitorLog WHERE RunID = @RunID;

    END TRY
    BEGIN CATCH
        SET @ErrorMessage = ERROR_MESSAGE();
        SET @EndTime = SYSDATETIME();

        INSERT INTO dbo.DBA_SPMonitorLog (ProcedureName, Params, DurationMs, Status, ErrorMessage)
        VALUES (@ProcedureName, @Params, DATEDIFF(MS, @StartTime, @EndTime), 'Failed', @ErrorMessage);

        PRINT 'Error monitoring SP: ' + @ErrorMessage;
    END CATCH

    -- Cleanup XE
    IF @EnableTracing = 1 AND EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = 'DBA_SPTrace')
        DROP EVENT SESSION DBA_SPTrace ON SERVER;
END
GO