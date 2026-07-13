-- Extra Cassandra table for the orders scenario (flink_jobs/orders_to_cassandra.yaml).
-- The telemetry scenario reuses cassandra/schema/schema.cql (sensor_rollups).
CREATE TABLE IF NOT EXISTS telemetry.order_rollups (
  shop_id       int,
  window_start  timestamp,
  sum_amount    double,
  avg_amount    double,
  max_amount    double,
  count_amount  bigint,
  PRIMARY KEY ((shop_id), window_start)
) WITH CLUSTERING ORDER BY (window_start DESC);
