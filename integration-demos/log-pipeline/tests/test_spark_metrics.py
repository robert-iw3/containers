import pytest

from test_elasticsearch_ingestion import wait_for_documents


@pytest.fixture(scope="module")
def metrics_present(es_client, es_metrics_index):
    return wait_for_documents(es_client, es_metrics_index, timeout_seconds=240, interval_seconds=5)


def test_metrics_index_receives_documents(metrics_present):
    assert metrics_present > 0


def test_metrics_document_schema(es_client, es_metrics_index, metrics_present):
    result = es_client.search(index=es_metrics_index, size=1, sort=[{"window_start": "desc"}])
    hits = result["hits"]["hits"]
    assert len(hits) == 1

    document = hits[0]["_source"]
    for field in (
        "window_start",
        "window_end",
        "service",
        "level",
        "event_count",
        "avg_duration_ms",
        "error_count",
        "distinct_hosts",
    ):
        assert field in document

    assert document["event_count"] >= 1
    assert document["avg_duration_ms"] >= 0


def test_metrics_aggregation_is_consistent(es_client, es_metrics_index, metrics_present):
    result = es_client.search(
        index=es_metrics_index,
        size=0,
        aggs={
            "total_events": {"sum": {"field": "event_count"}},
            "total_errors": {"sum": {"field": "error_count"}},
        },
    )
    total_events = result["aggregations"]["total_events"]["value"]
    total_errors = result["aggregations"]["total_errors"]["value"]

    assert total_events >= total_errors
    assert total_events > 0
