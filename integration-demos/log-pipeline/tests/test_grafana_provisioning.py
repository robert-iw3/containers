import os

import requests

GRAFANA_USER = os.environ.get("GRAFANA_ADMIN_USER", "admin")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_ADMIN_PASSWORD", "admin")


def auth():
    return (GRAFANA_USER, GRAFANA_PASSWORD)


def test_grafana_is_healthy(grafana_url):
    response = requests.get(f"{grafana_url}/api/health", timeout=10)
    assert response.ok
    assert response.json().get("database") == "ok"


def test_expected_datasources_are_provisioned(grafana_url):
    response = requests.get(f"{grafana_url}/api/datasources", auth=auth(), timeout=10)
    assert response.ok
    uids = {ds["uid"] for ds in response.json()}
    assert {"es-raw-logs", "es-metrics"}.issubset(uids)


def test_datasources_report_healthy(grafana_url):
    for uid in ("es-raw-logs", "es-metrics"):
        response = requests.get(
            f"{grafana_url}/api/datasources/uid/{uid}/health", auth=auth(), timeout=10
        )
        assert response.ok, f"{uid} health check failed: {response.text}"
        assert response.json().get("status") == "OK"


def test_dashboard_is_provisioned(grafana_url):
    response = requests.get(
        f"{grafana_url}/api/dashboards/uid/log-pipeline-overview", auth=auth(), timeout=10
    )
    assert response.ok
    dashboard = response.json()["dashboard"]
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    assert "Recent Error Logs" in panel_titles
