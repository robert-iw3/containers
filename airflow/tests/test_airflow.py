"""
Tests for the Airflow 3.x deployment and the telemetry pipeline DAGs.

Two layers:
  * Static config invariants (always run) -- guard the Airflow 3.x migration:
    api-server (not the removed `webserver`), the required dag-processor, the
    JWT/auth-manager/execution-API config, the arbitrary-UID PYTHONPATH fix, and
    the pipeline's idempotency/data-aware wiring, read straight from the source.
  * DagBag integrity (skipped if `airflow` isn't importable locally) -- parse the
    telemetry DAGs, assert no import errors, expected tasks, and asset wiring. The
    live run documented in the readme is the full end-to-end check.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "telemetry_pipeline"
COMPOSE = (ROOT / "docker-compose.yaml").read_text()

airflow_installed = importlib.util.find_spec("airflow") is not None


class TestComposeAirflow3Migration:
    """Airflow 3.x renamed/added commands and config vs 2.x -- lock the migration."""

    def test_uses_api_server_not_webserver(self):
        # `webserver` was removed in Airflow 3.x; the UI/API is served by `api-server`.
        assert "command: api-server" in COMPOSE
        assert re.search(r"command:\s*webserver", COMPOSE) is None
        assert "airflow-apiserver:" in COMPOSE

    def test_has_dag_processor_service(self):
        # The standalone dag-processor is required in Airflow 3.x.
        assert "airflow-dag-processor:" in COMPOSE
        assert "command: dag-processor" in COMPOSE

    def test_auth_manager_and_jwt_configured(self):
        assert "AIRFLOW__CORE__AUTH_MANAGER" in COMPOSE
        assert "FabAuthManager" in COMPOSE
        # JWT secret replaces the 2.x webserver secret key for inter-component auth.
        assert "AIRFLOW__API_AUTH__JWT_SECRET" in COMPOSE
        assert "AIRFLOW__WEBSERVER__SECRET_KEY" not in COMPOSE

    def test_execution_api_server_url_set(self):
        assert "AIRFLOW__CORE__EXECUTION_API_SERVER_URL" in COMPOSE

    def test_apiserver_healthcheck_uses_v2_monitor(self):
        assert "/api/v2/monitor/health" in COMPOSE

    def test_arbitrary_uid_pythonpath_fix(self):
        # Without this, `import airflow` fails for a non-50000 UID under rootless
        # podman/OpenShift (the entrypoint's HOME rewrite doesn't fire). See readme.
        assert "PYTHONPATH:" in COMPOSE
        assert "/home/airflow/.local/lib/python3.13/site-packages" in COMPOSE

    def test_init_is_not_double_exec(self):
        # The old init ran two execs, so user creation never happened; it must rely
        # on the entrypoint's _AIRFLOW_DB_MIGRATE/_AIRFLOW_WWW_USER_CREATE env vars.
        assert "_AIRFLOW_DB_MIGRATE" in COMPOSE
        assert "_AIRFLOW_WWW_USER_CREATE" in COMPOSE
        assert COMPOSE.count("exec /entrypoint") <= 1

    def test_celery_stack_present(self):
        assert "AIRFLOW__CORE__EXECUTOR: CeleryExecutor" in COMPOSE
        assert "command: celery worker" in COMPOSE
        assert "redis:" in COMPOSE

    def test_warehouse_connection_defined(self):
        assert "AIRFLOW_CONN_TELEMETRY_WAREHOUSE" in COMPOSE

    def test_pipeline_dirs_mounted_under_dags(self):
        assert "/opt/airflow/dags/telemetry_pipeline" in COMPOSE
        assert "/opt/airflow/dags/examples" in COMPOSE

    def test_tls_enabled_on_apiserver(self):
        # The api-server (UI/login + execution API) must serve HTTPS, and components
        # must trust the cert + hit the execution API over https.
        assert "AIRFLOW__API__SSL_CERT" in COMPOSE
        assert "AIRFLOW__API__SSL_KEY" in COMPOSE
        assert "https://airflow-apiserver:8080/execution/" in COMPOSE
        assert "SSL_CERT_FILE" in COMPOSE
        # healthcheck hits https with -k (self-signed).
        assert "https://localhost:8080/api/v2/monitor/health" in COMPOSE


class TestK8sManifest:
    """The k8s manifest must carry the same Airflow 3.x + TLS invariants as compose."""

    K8S = (ROOT / "k8s-deployment.yaml").read_text()

    def test_no_legacy_webserver(self):
        assert "webserver" not in self.K8S
        assert "api-server" in self.K8S

    def test_all_planes_present(self):
        for plane in ("api-server", "scheduler", "dag-processor", "triggerer", "celery"):
            assert plane in self.K8S, plane

    def test_worker_autoscaling(self):
        assert "HorizontalPodAutoscaler" in self.K8S
        assert "airflow-worker" in self.K8S

    def test_tls_wired(self):
        assert "AIRFLOW__API__SSL_CERT" in self.K8S
        assert "https://airflow-apiserver" in self.K8S
        assert "scheme: HTTPS" in self.K8S


class TestPipelineSource:
    """Static guarantees on the pipeline that matter for production correctness."""

    etl = (PIPELINE / "telemetry_etl.py").read_text()
    report = (PIPELINE / "telemetry_report.py").read_text()
    common = (PIPELINE / "common.py").read_text()

    def test_load_is_idempotent(self):
        # Idempotent load = DELETE the window before re-inserting, so retries/backfills
        # converge instead of duplicating rows.
        assert "DELETE FROM" in self.etl
        assert "CREATE TABLE IF NOT EXISTS" in self.etl

    def test_window_resolution_handles_manual_runs(self):
        # Airflow 3.x manual runs may have no data interval; extract must not assume it.
        assert 'context.get("data_interval_start")' in self.etl
        assert 'context["data_interval_start"]' not in self.etl

    def test_etl_publishes_asset(self):
        assert "outlets=[TELEMETRY_WINDOW]" in self.etl

    def test_report_is_asset_triggered(self):
        # Data-aware scheduling: no cron, triggered by the asset the ETL produces.
        assert "schedule=[TELEMETRY_WINDOW]" in self.report

    def test_shared_constants_live_in_non_dag_module(self):
        # common.py must not define a DAG, else importing it from the report has the
        # side effect of instantiating the ETL DAG under the wrong fileloc.
        assert "@dag" not in self.common
        assert "from common import" in self.etl
        assert "from common import" in self.report

    def test_quality_gate_present(self):
        assert "quality gate failed" in self.etl
        assert "MAX_BAD_FRACTION" in self.etl

    def test_anomaly_detection_present(self):
        assert "ANOMALY_Z" in self.etl


@pytest.mark.skipif(not airflow_installed, reason="airflow not installed in this venv")
class TestDagIntegrity:
    """Parse the DAGs the way the scheduler does and assert structure."""

    @pytest.fixture(scope="class")
    def dagbag(self):
        sys.path.insert(0, str(PIPELINE))
        from airflow.models.dagbag import DagBag

        # `include_examples` was removed from DagBag in Airflow 3.x; the pipeline
        # folder has no examples anyway.
        return DagBag(dag_folder=str(PIPELINE))

    def test_no_import_errors(self, dagbag):
        assert dagbag.import_errors == {}, dagbag.import_errors

    def test_expected_dags_present(self, dagbag):
        assert {"telemetry_etl", "telemetry_report"} <= set(dagbag.dag_ids)

    def test_etl_task_chain(self, dagbag):
        dag = dagbag.get_dag("telemetry_etl")
        assert {
            "resolve_window", "extract_telemetry", "validate",
            "transform", "load", "publish_metrics",
        } == set(dag.task_ids)

    def test_etl_has_retries_and_timeout(self, dagbag):
        dag = dagbag.get_dag("telemetry_etl")
        task = dag.get_task("load")
        assert task.retries >= 1
        assert task.execution_timeout is not None

    def test_no_cycles(self, dagbag):
        # get_dag triggers cycle detection in Airflow; an ill-formed graph raises.
        for dag_id in ("telemetry_etl", "telemetry_report"):
            assert dagbag.get_dag(dag_id) is not None
