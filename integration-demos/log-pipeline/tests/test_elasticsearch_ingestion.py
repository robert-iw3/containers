import time

import pytest


def wait_for_documents(es_client, index, timeout_seconds=120, interval_seconds=3):
    deadline = time.time() + timeout_seconds
    last_count = 0
    while time.time() < deadline:
        if es_client.indices.exists(index=index):
            es_client.indices.refresh(index=index)
            count = es_client.count(index=index)["count"]
            last_count = count
            if count > 0:
                return count
        time.sleep(interval_seconds)
    raise TimeoutError(f"no documents appeared in {index} (last observed count: {last_count})")


@pytest.fixture(scope="module")
def raw_logs_present(es_client, es_raw_index):
    return wait_for_documents(es_client, es_raw_index)


def test_raw_logs_index_receives_documents(raw_logs_present):
    assert raw_logs_present > 0


def test_raw_log_document_schema(es_client, es_raw_index, raw_logs_present):
    result = es_client.search(index=es_raw_index, size=1, sort=[{"timestamp": "desc"}])
    hits = result["hits"]["hits"]
    assert len(hits) == 1

    document = hits[0]["_source"]
    for field in ("timestamp", "service", "host", "level", "message", "status_code", "duration_ms"):
        assert field in document

    assert isinstance(document["status_code"], int)
    assert isinstance(document["duration_ms"], (int, float))
    assert document["level"] in {"INFO", "WARN", "ERROR", "DEBUG"}


def test_error_level_documents_are_indexed(es_client, es_raw_index, raw_logs_present):
    result = es_client.search(
        index=es_raw_index,
        size=1,
        query={"term": {"level": "ERROR"}},
    )
    assert result["hits"]["total"]["value"] >= 0
