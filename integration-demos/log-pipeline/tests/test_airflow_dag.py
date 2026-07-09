import json
import time

import pytest

DAG_ID = "log_pipeline_daily_rollup"


def test_dag_has_no_import_errors(run_in_airflow):
    result = run_in_airflow("airflow", "dags", "list-import-errors", "-o", "json", check=False)
    errors = json.loads(result.stdout)
    assert errors == [], f"DAG import errors: {errors}"


def test_dag_is_registered(run_in_airflow):
    result = run_in_airflow("airflow", "dags", "list", "-o", "json")
    dag_ids = {row["dag_id"] for row in json.loads(result.stdout)}
    assert DAG_ID in dag_ids


@pytest.mark.timeout(180)
def test_dag_run_completes_successfully(run_in_airflow, es_client):
    run_in_airflow("airflow", "dags", "unpause", DAG_ID)
    trigger = run_in_airflow("airflow", "dags", "trigger", DAG_ID, "-o", "json")
    triggered = json.loads(trigger.stdout)
    run_id = triggered[0]["dag_run_id"] if isinstance(triggered, list) else triggered["dag_run_id"]

    deadline = time.time() + 150
    state = None
    while time.time() < deadline:
        status = run_in_airflow(
            "airflow", "dags", "state", DAG_ID, run_id
        )
        state = status.stdout.strip()
        if state in {"success", "failed"}:
            break
        time.sleep(5)

    assert state == "success", f"DAG run ended in state: {state}"

    es_client.indices.refresh(index="logs-daily-summary")
    count = es_client.count(index="logs-daily-summary")["count"]
    assert count > 0
