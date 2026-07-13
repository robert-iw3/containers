#!/usr/bin/env python3
"""Kafka -> Cassandra sink for the integration pipeline.

Consumes the windowed rollups Flink writes to the `sensor-rollups` topic and upserts
them into Cassandra `telemetry.sensor_rollups`. This is the final hop of
producer -> Kafka -> Flink -> Kafka -> Cassandra.

    python3 cassandra_sink.py --bootstrap kafka1:9092 --cassandra cassandra --topic sensor-rollups
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from cassandra.cluster import Cluster
from cassandra.query import BatchStatement
from kafka import KafkaConsumer

INSERT = """
INSERT INTO telemetry.sensor_rollups
  (sensor_id, window_start, metric, avg_value, min_value, max_value,
   count_value, stddev_value, anomaly)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def parse_ts(v: str) -> datetime:
    # Flink JSON emits TIMESTAMP(3) as "YYYY-MM-DD HH:MM:SS(.fff)".
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.fromisoformat(v)


def main() -> None:
    ap = argparse.ArgumentParser(description="Kafka sensor-rollups -> Cassandra sink")
    ap.add_argument("--bootstrap", default="kafka1:9092")
    ap.add_argument("--cassandra", default="cassandra")
    ap.add_argument("--topic", default="sensor-rollups")
    ap.add_argument("--group", default="cassandra-sink")
    ap.add_argument("--flush", type=int, default=50, help="rows per batch")
    args = ap.parse_args()

    cluster = Cluster([h.strip() for h in args.cassandra.split(",")])
    session = cluster.connect("telemetry")
    prepared = session.prepare(INSERT)

    consumer = KafkaConsumer(
        args.topic,
        bootstrap_servers=args.bootstrap.split(","),
        group_id=args.group,
        auto_offset_reset="earliest",
        value_deserializer=lambda b: json.loads(b.decode()),
    )
    print(f"cassandra-sink: {args.topic}@{args.bootstrap} -> {args.cassandra}/telemetry.sensor_rollups")

    batch = BatchStatement()
    n = 0
    written = 0
    for msg in consumer:
        r = msg.value
        batch.add(prepared, (
            r["sensor_id"],
            parse_ts(r["window_start"]),
            r["metric"],
            r.get("avg_value"),
            r.get("min_value"),
            r.get("max_value"),
            r.get("count_value"),
            r.get("stddev_pop_value"),
            r.get("value_anomaly"),
        ))
        n += 1
        if n >= args.flush:
            session.execute(batch)
            written += n
            batch = BatchStatement()
            n = 0
            print(f"  upserted {written} rollups")


if __name__ == "__main__":
    main()
