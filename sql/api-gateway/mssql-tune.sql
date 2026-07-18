-- Shard tuning applied once at container startup (idempotent). Targets the
-- pressure points a stress workload creates: parallelism, plan-cache churn,
-- parameter sniffing, tempdb spills and index fragmentation.
SET NOCOUNT ON;

EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;

-- Bound parallelism so short OLTP queries don't fan out; raise the cost
-- threshold so only genuinely expensive plans go parallel.
EXEC sp_configure 'max degree of parallelism', $(MAXDOP);
EXEC sp_configure 'cost threshold for parallelism', $(COST_THRESHOLD);
-- Single-use ad-hoc plans store a stub instead of the full plan (cache bloat).
EXEC sp_configure 'optimize for ad hoc workloads', 1;
-- Cap server memory so the engine never starves the container/OS.
EXEC sp_configure 'max server memory (MB)', $(MAX_MEMORY_MB);
-- Leave a little free space per page to reduce page splits / fragmentation.
EXEC sp_configure 'fill factor (%)', 90;
RECONFIGURE;

-- Add tempdb data files (one per core, up to the requested count) to spread
-- allocation contention and absorb sort/hash spills.
DECLARE @target int = $(TEMPDB_FILES);
DECLARE @have int = (SELECT COUNT(*) FROM sys.master_files WHERE database_id = 2 AND type = 0);
DECLARE @i int = @have, @sql nvarchar(400);
WHILE @i < @target
BEGIN
    SET @i += 1;
    SET @sql = N'ALTER DATABASE tempdb ADD FILE (NAME = N''tempdev' + CAST(@i AS nvarchar(4))
        + ''', FILENAME = N''/var/opt/mssql/data/tempdev' + CAST(@i AS nvarchar(4))
        + '.ndf'', SIZE = 64MB, FILEGROWTH = 64MB)';
    BEGIN TRY EXEC (@sql); END TRY BEGIN CATCH /* file already present */ END CATCH;
END;

-- Tune the model database so every database the gateway creates inherits:
--   * Query Store  -> captures plans, enables parameter-sniffing analysis
--   * RCSI         -> readers don't block writers under concurrency
--   * CHECKSUM     -> torn-page detection
--   * async stats  -> auto-update statistics without stalling queries
ALTER DATABASE model SET QUERY_STORE = ON;
ALTER DATABASE model SET QUERY_STORE (
    OPERATION_MODE = READ_WRITE,
    QUERY_CAPTURE_MODE = AUTO,
    MAX_STORAGE_SIZE_MB = 512
);
ALTER DATABASE model SET READ_COMMITTED_SNAPSHOT ON;
ALTER DATABASE model SET PAGE_VERIFY CHECKSUM;
ALTER DATABASE model SET AUTO_UPDATE_STATISTICS_ASYNC ON;
