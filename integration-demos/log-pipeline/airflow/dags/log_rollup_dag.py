import os
from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task
from elasticsearch import Elasticsearch

ES_HOST = os.environ.get("ES_HOST", "http://elasticsearch:9200")
METRICS_INDEX = os.environ.get("ES_METRICS_INDEX", "logs-metrics-1m")
RAW_INDEX_PREFIX = os.environ.get("ES_RAW_INDEX", "logs-raw")
SUMMARY_INDEX = os.environ.get("ES_SUMMARY_INDEX", "logs-daily-summary")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))


def es_client():
    return Elasticsearch(ES_HOST)


@dag(
    dag_id="log_pipeline_daily_rollup",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["log-pipeline"],
)
def log_pipeline_daily_rollup():
    @task
    def build_daily_summary(logical_date=None):
        client = es_client()
        target_day = (logical_date or datetime.now(timezone.utc)).date().isoformat()

        response = client.search(
            index=METRICS_INDEX,
            size=0,
            query={
                "range": {
                    "window_start": {
                        "gte": f"{target_day}T00:00:00Z",
                        "lt": f"{target_day}T23:59:59Z",
                    }
                }
            },
            aggs={
                "by_service": {
                    "terms": {"field": "service", "size": 50},
                    "aggs": {
                        "total_events": {"sum": {"field": "event_count"}},
                        "total_errors": {"sum": {"field": "error_count"}},
                        "avg_duration_ms": {"avg": {"field": "avg_duration_ms"}},
                    },
                },
                "total_events": {"sum": {"field": "event_count"}},
                "total_errors": {"sum": {"field": "error_count"}},
            },
        )

        aggregations = response["aggregations"]
        total_events = aggregations["total_events"]["value"] or 0
        total_errors = aggregations["total_errors"]["value"] or 0
        error_rate = (total_errors / total_events) if total_events else 0.0

        per_service = [
            {
                "service": bucket["key"],
                "event_count": bucket["total_events"]["value"] or 0,
                "error_count": bucket["total_errors"]["value"] or 0,
                "avg_duration_ms": bucket["avg_duration_ms"]["value"] or 0.0,
            }
            for bucket in aggregations["by_service"]["buckets"]
        ]

        document = {
            "date": target_day,
            "total_events": total_events,
            "total_errors": total_errors,
            "error_rate": error_rate,
            "services": per_service,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        client.index(index=SUMMARY_INDEX, id=target_day, document=document)
        return document

    @task
    def apply_retention():
        client = es_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()

        for index_pattern in (f"{RAW_INDEX_PREFIX}*", f"{METRICS_INDEX}*"):
            if not client.indices.exists(index=index_pattern):
                continue
            client.delete_by_query(
                index=index_pattern,
                query={"range": {"timestamp": {"lt": cutoff}}},
                conflicts="proceed",
                ignore_unavailable=True,
            )

    summary = build_daily_summary()
    retention = apply_retention()
    summary >> retention


log_pipeline_daily_rollup()
