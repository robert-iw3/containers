"""
Production IoT-telemetry ETL pipeline (Airflow 3.x TaskFlow API).

Extract -> validate/quality-gate -> transform (windowed rollups + anomaly scoring)
-> load (idempotent upsert into a Postgres warehouse) -> publish an Asset so
downstream, data-aware DAGs (see ``telemetry_report.py``) run only when a window
has actually landed.

The extractor is deterministic per data interval (seeded from the window start),
so re-running any interval reproduces the same rows and the load is idempotent --
the properties you want from a backfillable production pipeline. Swap
``extract_telemetry`` for a real source (Kafka/MQTT/ScyllaDB/S3) and keep the rest.

Only the Python standard library is used inside tasks, so the DAG parses and runs
on a stock Airflow image with the Postgres provider.

resolve_window → extract → validate → transform(rollup+anomaly) → load(idempotent Postgres) → Asset → report
"""

from __future__ import annotations

import random
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from airflow.sdk import dag, task

from common import ROLLUP_TABLE, TELEMETRY_WINDOW, WAREHOUSE_CONN_ID

WINDOW_MINUTES = 15

# Fleet of simulated edge sensors and the metric each emits with a plausible range.
SENSORS = [f"sensor-{i:03d}" for i in range(1, 25)]
METRICS = {
    "temperature_c": (18.0, 27.0),
    "humidity_pct": (30.0, 65.0),
    "vibration_mm_s": (0.1, 4.5),
    "power_w": (40.0, 240.0),
}
# Quality gate: reject a window if more than this fraction of rows are bad.
MAX_BAD_FRACTION = 0.05
# Anomaly gate: |z-score| beyond this flags a reading as anomalous.
ANOMALY_Z = 3.0

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=15),
}


@dag(
    dag_id="telemetry_etl",
    description="IoT telemetry ETL: extract -> validate -> rollup/anomaly -> warehouse",
    schedule="*/15 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["telemetry", "etl", "production"],
)
def telemetry_etl():
    @task
    def resolve_window(**context: Any) -> dict[str, str]:
        """Resolve the [start, end) window to process, once, for the whole run.

        Scheduled runs carry a data interval; Airflow 3.x manual runs may have a
        null logical date and no interval, so fall back to the most recent closed
        WINDOW_MINUTES boundary. Computing it here (not per task) keeps extract and
        load consistent."""
        start = context.get("data_interval_start")
        end = context.get("data_interval_end")
        if start is None or end is None:
            now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            end = now - timedelta(minutes=now.minute % WINDOW_MINUTES)
            start = end - timedelta(minutes=WINDOW_MINUTES)
        print(f"processing window {start.isoformat()} .. {end.isoformat()}")
        return {"start": start.isoformat(), "end": end.isoformat()}

    @task
    def extract_telemetry(window: dict[str, str]) -> list[dict[str, Any]]:
        """Pull the batch of raw readings for this window.

        Deterministic per window (seeded from the window start) so backfills and
        retries are reproducible. ~1 reading/sensor/metric/minute over the window.
        """
        start = datetime.fromisoformat(window["start"])
        end = datetime.fromisoformat(window["end"])
        rng = random.Random(int(start.timestamp()))
        minutes = max(1, int((end - start).total_seconds() // 60))

        readings: list[dict[str, Any]] = []
        for minute in range(minutes):
            ts = (start + timedelta(minutes=minute)).isoformat()
            for sensor in SENSORS:
                for metric, (lo, hi) in METRICS.items():
                    value: Any = round(rng.uniform(lo, hi), 3)
                    # Inject a little real-world mess: occasional nulls and spikes.
                    roll = rng.random()
                    if roll < 0.01:
                        value = None
                    elif roll < 0.02:
                        value = round(hi * rng.uniform(3.0, 6.0), 3)  # spike
                    readings.append(
                        {"sensor_id": sensor, "ts": ts, "metric": metric, "value": value}
                    )
        print(f"extracted {len(readings)} raw readings for {start} .. {end}")
        return readings

    @task
    def validate(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Schema + quality gate. Drops null/malformed rows; fails the run if the
        bad fraction exceeds the SLA so downstream never loads a poisoned window."""
        clean: list[dict[str, Any]] = []
        bad = 0
        seen: set[tuple[str, str, str]] = set()
        for r in readings:
            key = (r.get("sensor_id"), r.get("ts"), r.get("metric"))
            if None in key or key in seen:
                bad += 1
                continue
            seen.add(key)
            value = r.get("value")
            if not isinstance(value, (int, float)):
                bad += 1
                continue
            clean.append(r)

        total = len(readings) or 1
        bad_fraction = bad / total
        print(f"validated: {len(clean)} clean, {bad} rejected ({bad_fraction:.2%})")
        if bad_fraction > MAX_BAD_FRACTION:
            raise ValueError(
                f"quality gate failed: {bad_fraction:.2%} bad rows > "
                f"{MAX_BAD_FRACTION:.2%} threshold"
            )
        return clean

    @task
    def transform(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Window the readings into per-(sensor, metric) rollups and flag anomalies
        via z-score against that group's own distribution."""
        groups: dict[tuple[str, str], list[float]] = {}
        for r in readings:
            groups.setdefault((r["sensor_id"], r["metric"]), []).append(float(r["value"]))

        rollups: list[dict[str, Any]] = []
        for (sensor_id, metric), values in groups.items():
            n = len(values)
            mean = statistics.fmean(values)
            stdev = statistics.pstdev(values) if n > 1 else 0.0
            anomalies = (
                sum(1 for v in values if stdev and abs((v - mean) / stdev) > ANOMALY_Z)
                if stdev
                else 0
            )
            ordered = sorted(values)
            p95 = ordered[min(n - 1, int(round(0.95 * (n - 1))))]
            rollups.append(
                {
                    "sensor_id": sensor_id,
                    "metric": metric,
                    "sample_count": n,
                    "avg_value": round(mean, 4),
                    "min_value": round(min(values), 4),
                    "max_value": round(max(values), 4),
                    "p95_value": round(p95, 4),
                    "stdev_value": round(stdev, 4),
                    "anomaly_count": anomalies,
                }
            )
        print(f"transformed into {len(rollups)} rollups")
        return rollups

    @task(outlets=[TELEMETRY_WINDOW])
    def load(rollups: list[dict[str, Any]], window: dict[str, str]) -> int:
        """Idempotent load: ensure schema, then delete+insert this window's rows so
        re-runs converge. Publishes the TELEMETRY_WINDOW asset on success."""
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        window_start = window["start"]
        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)

        hook.run(
            f"""
            CREATE TABLE IF NOT EXISTS {ROLLUP_TABLE} (
                window_start   TIMESTAMPTZ NOT NULL,
                sensor_id      TEXT        NOT NULL,
                metric         TEXT        NOT NULL,
                sample_count   INTEGER     NOT NULL,
                avg_value      DOUBLE PRECISION,
                min_value      DOUBLE PRECISION,
                max_value      DOUBLE PRECISION,
                p95_value      DOUBLE PRECISION,
                stdev_value    DOUBLE PRECISION,
                anomaly_count  INTEGER     NOT NULL DEFAULT 0,
                loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (window_start, sensor_id, metric)
            );
            """
        )
        # Idempotent for backfills/retries: clear the window before reinserting.
        hook.run(f"DELETE FROM {ROLLUP_TABLE} WHERE window_start = %s", parameters=(window_start,))

        if rollups:
            rows = [
                (
                    window_start,
                    r["sensor_id"],
                    r["metric"],
                    r["sample_count"],
                    r["avg_value"],
                    r["min_value"],
                    r["max_value"],
                    r["p95_value"],
                    r["stdev_value"],
                    r["anomaly_count"],
                )
                for r in rollups
            ]
            target_fields = [
                "window_start", "sensor_id", "metric", "sample_count", "avg_value",
                "min_value", "max_value", "p95_value", "stdev_value", "anomaly_count",
            ]
            hook.insert_rows(
                table=ROLLUP_TABLE, rows=rows, target_fields=target_fields, commit_every=500
            )
        print(f"loaded {len(rollups)} rollups for window {window_start}")
        return len(rollups)

    @task
    def publish_metrics(loaded: int) -> None:
        """Final SLA assertion: a healthy window must land rollups."""
        print(f"pipeline complete: {loaded} rollups persisted")
        if loaded <= 0:
            raise ValueError("no rollups were loaded -- investigate upstream extract/validate")

    window = resolve_window()
    raw = extract_telemetry(window)
    clean = validate(raw)
    rollups = transform(clean)
    loaded = load(rollups, window)
    publish_metrics(loaded)


telemetry_etl()
