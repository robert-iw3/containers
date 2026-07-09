-- IoT / data-pipeline telemetry schema for ScyllaDB.
-- Structured time-series readings + an unstructured JSON/blob payload column,
-- so the same store handles both shaped sensor data and arbitrary event bodies.
--
-- Replication factor 3 matches the 3-node production cluster; NetworkTopologyStrategy
-- so the keyspace survives the move to multiple datacenters without a rewrite.

CREATE KEYSPACE IF NOT EXISTS telemetry
  WITH replication = {'class': 'NetworkTopologyStrategy', 'replication_factor': 3}
  AND durable_writes = true;

-- Raw ingest: every event lands here first, partitioned by device and hour so a
-- single partition never grows unbounded (hot-partition protection for high-rate
-- IoT streams). payload holds the unstructured body; the typed columns are the
-- structured projection the ETL fills in.
CREATE TABLE IF NOT EXISTS telemetry.raw_events (
  device_id    text,
  bucket       text,          -- yyyy-MM-dd-HH, keeps partitions bounded
  event_time   timestamp,
  event_id     timeuuid,
  metric       text,
  value        double,
  unit         text,
  payload      text,          -- unstructured JSON / arbitrary body
  ingested_at  timestamp,
  PRIMARY KEY ((device_id, bucket), event_time, event_id)
) WITH CLUSTERING ORDER BY (event_time DESC, event_id DESC)
  AND default_time_to_live = 2592000        -- 30d raw retention
  -- TimeWindowCompactionStrategy is the correct strategy for append-only
  -- time-series: whole SSTables age out with the TTL instead of being
  -- rewritten by size-tiered compaction, so write amplification stays flat
  -- at high ingest rates and expired data is dropped cheaply.
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  }
  AND compression = {'sstable_compression': 'ZstdCompressor'}
  AND gc_grace_seconds = 3600
  AND speculative_retry = '99.0PERCENTILE';

-- Structured, ETL-cleaned rollup used by apps/frontends/dashboards. Downsampled
-- per-minute aggregates keep reads cheap for any client.
CREATE TABLE IF NOT EXISTS telemetry.metrics_1m (
  device_id   text,
  metric      text,
  bucket      text,           -- yyyy-MM-dd
  minute      timestamp,
  count       bigint,
  sum         double,
  min         double,
  max         double,
  avg         double,
  PRIMARY KEY ((device_id, metric, bucket), minute)
) WITH CLUSTERING ORDER BY (minute DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 7
  }
  AND compression = {'sstable_compression': 'ZstdCompressor'}
  AND default_time_to_live = 7776000;      -- 90d rollup retention

-- Device registry so any API/app can enumerate and describe devices.
CREATE TABLE IF NOT EXISTS telemetry.devices (
  device_id   text PRIMARY KEY,
  kind        text,
  location    text,
  metadata    text,           -- unstructured device attributes (JSON)
  registered_at timestamp,
  last_seen   timestamp
);

-- Dead-letter for events the ETL could not parse/transform, so no data is lost.
CREATE TABLE IF NOT EXISTS telemetry.dead_letter (
  device_id   text,
  bucket      text,
  event_time  timestamp,
  event_id    timeuuid,
  reason      text,
  payload     text,
  PRIMARY KEY ((device_id, bucket), event_time, event_id)
) WITH CLUSTERING ORDER BY (event_time DESC, event_id DESC)
  AND default_time_to_live = 604800      -- 7d
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'HOURS',
    'compaction_window_size': 12
  };
