"""
Downstream, data-aware reporting DAG.

Runs *only* when ``telemetry_etl`` publishes a new window to the
``telemetry://warehouse/sensor_rollups`` Asset -- no schedule, no polling. It
summarises the freshly-loaded window: fleet-wide sample volume and the sensors
with the most anomalies, the kind of thing an alerting/BI layer consumes.
"""

from __future__ import annotations

from typing import Any

from airflow.sdk import dag, task

from common import ROLLUP_TABLE, TELEMETRY_WINDOW, WAREHOUSE_CONN_ID


@dag(
    dag_id="telemetry_report",
    description="Data-aware summary of the latest telemetry window (Asset-triggered)",
    schedule=[TELEMETRY_WINDOW],
    catchup=False,
    max_active_runs=1,
    tags=["telemetry", "reporting", "production"],
)
def telemetry_report():
    @task
    def summarize_latest_window() -> dict[str, Any]:
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)
        latest = hook.get_first(f"SELECT max(window_start) FROM {ROLLUP_TABLE}")
        if not latest or latest[0] is None:
            print("no telemetry windows loaded yet")
            return {"window_start": None, "rows": 0}
        window_start = latest[0]

        totals = hook.get_first(
            f"""
            SELECT count(*), coalesce(sum(sample_count), 0), coalesce(sum(anomaly_count), 0)
            FROM {ROLLUP_TABLE} WHERE window_start = %s
            """,
            parameters=(window_start,),
        )
        top = hook.get_records(
            f"""
            SELECT sensor_id, metric, anomaly_count
            FROM {ROLLUP_TABLE}
            WHERE window_start = %s AND anomaly_count > 0
            ORDER BY anomaly_count DESC LIMIT 5
            """,
            parameters=(window_start,),
        )

        rollup_rows, samples, anomalies = totals
        print(f"window {window_start}: {rollup_rows} rollups, {samples} samples, {anomalies} anomalies")
        for sensor_id, metric, count in top:
            print(f"  anomaly: {sensor_id}/{metric} -> {count}")
        return {
            "window_start": str(window_start),
            "rollup_rows": rollup_rows,
            "samples": samples,
            "anomalies": anomalies,
        }

    summarize_latest_window()


telemetry_report()
