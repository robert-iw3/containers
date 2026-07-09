"""
Shared constants for the telemetry pipeline DAGs.

Kept in a non-DAG module so importing it (from telemetry_report) does not have the
side effect of instantiating the telemetry_etl DAG.
"""

from __future__ import annotations

from airflow.sdk import Asset

# Data-aware scheduling handle: telemetry_etl produces it, telemetry_report consumes it.
TELEMETRY_WINDOW = Asset("telemetry://warehouse/sensor_rollups")

WAREHOUSE_CONN_ID = "telemetry_warehouse"
ROLLUP_TABLE = "telemetry_sensor_rollups"
