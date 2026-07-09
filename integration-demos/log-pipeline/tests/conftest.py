import os
import subprocess
import time
from pathlib import Path

import pytest
import requests
from confluent_kafka.admin import AdminClient
from elasticsearch import Elasticsearch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("TEST_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ES_URL = os.environ.get("TEST_ES_URL", "http://localhost:9200")
GRAFANA_URL = os.environ.get("TEST_GRAFANA_URL", "http://localhost:3000")
AIRFLOW_CONTAINER = os.environ.get("TEST_AIRFLOW_CONTAINER", "log-pipeline-airflow")

KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "app-logs")
ES_RAW_INDEX = os.environ.get("ES_RAW_INDEX", "logs-raw")
ES_METRICS_INDEX = os.environ.get("ES_METRICS_INDEX", "logs-metrics-1m")


def compose(*args):
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def wait_for(predicate, timeout_seconds, interval_seconds=2, description="condition"):
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(interval_seconds)
    raise TimeoutError(f"timed out waiting for {description}: {last_error}")


@pytest.fixture(scope="session", autouse=True)
def compose_stack():
    keep_stack = os.environ.get("LOG_PIPELINE_KEEP_STACK") == "1"
    skip_bootstrap = os.environ.get("LOG_PIPELINE_SKIP_BOOTSTRAP") == "1"

    if not skip_bootstrap:
        compose("up", "-d", "--build")

    def elasticsearch_ready():
        response = requests.get(f"{ES_URL}/_cluster/health", timeout=5)
        return response.ok and response.json().get("status") in {"yellow", "green"}

    def grafana_ready():
        response = requests.get(f"{GRAFANA_URL}/api/health", timeout=5)
        return response.ok

    def kafka_ready():
        admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
        metadata = admin.list_topics(timeout=5)
        return metadata is not None

    wait_for(elasticsearch_ready, timeout_seconds=180, description="elasticsearch to be healthy")
    wait_for(kafka_ready, timeout_seconds=120, description="kafka to be reachable")
    wait_for(grafana_ready, timeout_seconds=180, description="grafana to be healthy")

    yield

    if not keep_stack:
        compose("down", "-v")


@pytest.fixture(scope="session")
def es_client():
    return Elasticsearch(ES_URL)


@pytest.fixture(scope="session")
def kafka_admin():
    return AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


@pytest.fixture(scope="session")
def kafka_bootstrap_servers():
    return KAFKA_BOOTSTRAP_SERVERS


@pytest.fixture(scope="session")
def kafka_topic():
    return KAFKA_TOPIC


@pytest.fixture(scope="session")
def es_raw_index():
    return ES_RAW_INDEX


@pytest.fixture(scope="session")
def es_metrics_index():
    return ES_METRICS_INDEX


@pytest.fixture(scope="session")
def grafana_url():
    return GRAFANA_URL


@pytest.fixture(scope="session")
def airflow_container():
    return AIRFLOW_CONTAINER


@pytest.fixture
def run_in_airflow():
    def _run(*args, timeout=60, check=True):
        result = subprocess.run(
            ["docker", "exec", AIRFLOW_CONTAINER, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        return result

    return _run
