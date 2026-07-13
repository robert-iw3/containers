-- Declarative Cassandra schema, applied by the schema-init service
-- (docker compose run --rm schema-init) or scripts/apply_schema.sh.
-- RF=3 across dc1 (matches the 3-node cluster). Edit and re-apply idempotently.

CREATE KEYSPACE IF NOT EXISTS telemetry
  WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3};

-- Windowed sensor rollups produced by the Kafka -> Flink -> Cassandra pipeline.
-- Partitioned by sensor so a sensor's recent windows are a single-partition read;
-- clustered by window (newest first) then metric.
CREATE TABLE IF NOT EXISTS telemetry.sensor_rollups (
  sensor_id     text,
  window_start  timestamp,
  metric        text,
  avg_value     double,
  min_value     double,
  max_value     double,
  count_value   bigint,
  stddev_value  double,
  anomaly       int,
  PRIMARY KEY ((sensor_id), window_start, metric)
) WITH CLUSTERING ORDER BY (window_start DESC, metric ASC)
  AND default_time_to_live = 2592000            -- 30d
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'HOURS',
                    'compaction_window_size': 24};

-- Optional raw landing table (high write throughput, TTL'd short).
CREATE TABLE IF NOT EXISTS telemetry.raw_events (
  sensor_id   text,
  event_time  timestamp,
  metric      text,
  value       double,
  PRIMARY KEY ((sensor_id), event_time, metric)
) WITH CLUSTERING ORDER BY (event_time DESC, metric ASC)
  AND default_time_to_live = 259200             -- 3d
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'HOURS',
                    'compaction_window_size': 6};
