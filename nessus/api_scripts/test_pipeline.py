import pytest
import json
import io
from unittest.mock import MagicMock, patch
from vuln_pipeline import (
    schedule_scans, assess_scans, prioritize_vulns, generate_remediation_reports,
    log_to_cloudwatch, verify_remediation, get_param, nessus_client
)
from tenable.nessus import Nessus

# Mock TOML config
MOCK_SCAN_TOML = """
[scan1]
name = "Test Scan"
enabled = true
text_targets = "192.168.1.0/24"
uuid = "731a8e52-3ea6-a291-2adf-1567a46550a4"
"""

MOCK_NESSUS_CONFIG_TOML = """
[nessus]
url = "https://mock-nessus:8834"
verify_ssl = false
folder_id = 3
[nessus.api_keys]
access_key = "mock_access_key"
secret_key = "mock_secret_key"
[nessus.report]
formats = ["json", "csv", "html", "nessus"]
chapters = ["vuln_by_host"]
db_password = "nessus"
[ticketing.jira]
url = "https://mock-jira"
token = "mock_jira_token"
project_key = "VULN"
[ticketing.servicenow]
url = "https://mock-servicenow"
username = "mock_sn_user"
password = "mock_sn_pass"
"""

@pytest.fixture
def mock_toml(tmp_path):
    scan_file = tmp_path / "scan.toml"
    scan_file.write_text(MOCK_SCAN_TOML)
    nessus_file = tmp_path / "nessus_config.toml"
    nessus_file.write_text(MOCK_NESSUS_CONFIG_TOML)
    return scan_file, nessus_file

@pytest.fixture
def mock_nessus():
    nessus = MagicMock(spec=Nessus)
    nessus.policies.list.return_value = [{'id': 1, 'name': 'standard_scan'}]
    nessus.scans.list.return_value = [{'id': 1, 'name': 'Test Scan', 'status': 'completed'}]
    nessus.scans.export_request.return_value = 123
    nessus.scans.export_status.return_value = 'ready'
    nessus.scans.export_download.return_value = (
        "plugin_name,severity,cvss,solution\n"
        "Test Vuln,3,7.5,Apply patch\n"
        "Low Vuln,1,2.0,Update config"
    )
    nessus.scans.create.return_value = {'id': 1}
    return nessus

@pytest.fixture
def mock_aws():
    ssm = MagicMock()
    ssm.get_parameter.side_effect = Exception("Parameter not found")
    logs = MagicMock()
    logs.describe_log_streams.return_value = {'logStreams': [{'uploadSequenceToken': '0'}]}
    return ssm, logs

@pytest.fixture
def mock_jira():
    jira = MagicMock()
    jira.create_issue.return_value = MagicMock(id='JIRA-123')
    return jira

@pytest.fixture
def mock_servicenow():
    sn = MagicMock()
    sn.create_incident.return_value = {'sys_id': 'INC123'}
    return sn

@patch('vuln_pipeline.toml.load')
@patch('vuln_pipeline.nessus_client')
def test_schedule_scans(mock_nessus_client, mock_toml_load, mock_toml, mock_nessus):
    mock_toml_load.side_effect = [
        {'scan1': {'name': 'Test Scan', 'enabled': True, 'text_targets': '192.168.1.0/24', 'uuid': '731a8e52-3ea6-a291-2adf-1567a46550a4'}},
        json.loads(MOCK_NESSUS_CONFIG_TOML)
    ]
    mock_nessus_client.return_value = mock_nessus
    result = schedule_scans(str(mock_toml[0]))
    assert len(result) == 1
    assert result[0]['id'] == 1
    mock_nessus.scans.create.assert_called()

@patch('vuln_pipeline.toml.load')
@patch('vuln_pipeline.nessus_client')
def test_assess_scans(mock_nessus_client, mock_toml_load, mock_toml, mock_nessus):
    mock_toml_load.return_value = json.loads(MOCK_NESSUS_CONFIG_TOML)
    mock_nessus_client.return_value = mock_nessus
    results = assess_scans(min_severity=1)
    assert len(results) == 1
    assert results[0]['scan_id'] == 1
    assert len(results[0]['vulns']) == 1  # Only severity >= 1
    assert results[0]['vulns'][0]['plugin_name'] == 'Test Vuln'

def test_prioritize_vulns():
    assessments = [{
        'scan_id': 1,
        'name': 'Test Scan',
        'vulns': [
            {'plugin_name': 'Test Vuln', 'severity': '3', 'cvss': '7.5'},
            {'plugin_name': 'Low Vuln', 'severity': '1', 'cvss': '2.0'}
        ]
    }]
    prioritized = prioritize_vulns(assessments)
    assert len(prioritized) == 1
    assert prioritized[0]['prioritized_vulns'][0]['plugin_name'] == 'Test Vuln'

@patch('vuln_pipeline.toml.load')
@patch('vuln_pipeline.nessus_client')
@patch('vuln_pipeline.get_jira_client')
@patch('vuln_pipeline.get_servicenow_client')
def test_generate_remediation_reports(mock_sn, mock_jira, mock_nessus_client, mock_toml_load, tmp_path, mock_nessus, mock_jira_client, mock_servicenow_client):
    mock_toml_load.return_value = json.loads(MOCK_NESSUS_CONFIG_TOML)
    mock_nessus_client.return_value = mock_nessus
    mock_jira.return_value = mock_jira_client
    mock_sn.return_value = mock_servicenow_client
    prioritized = [{'scan_id': 1, 'prioritized_vulns': [{'plugin_name': 'Test Vuln', 'severity': '3', 'cvss': '7.5', 'solution': 'Apply patch'}]}]
    generate_remediation_reports(prioritized, str(tmp_path))
    assert (tmp_path / '1_remediation.json').exists()
    assert (tmp_path / '1_remediation.csv').exists()
    assert (tmp_path / '1_remediation.html').exists()
    assert (tmp_path / '1_remediation.nessus').exists()
    mock_jira_client.create_issue.assert_called()
    mock_servicenow_client.create_incident.assert_called()

@patch('vuln_pipeline.logs_client')
def test_log_to_cloudwatch(mock_logs_client, mock_aws):
    mock_logs_client.return_value = mock_aws[1]
    data = [{'scan_id': 1, 'prioritized_vulns': [{'plugin_name': 'Test Vuln'}]}]
    log_to_cloudwatch(data)
    mock_aws[1].put_log_events.assert_called()

@patch('vuln_pipeline.toml.load')
@patch('vuln_pipeline.nessus_client')
def test_verify_remediation(mock_nessus_client, mock_toml_load, mock_toml, mock_nessus):
    mock_toml_load.return_value = json.loads(MOCK_NESSUS_CONFIG_TOML)
    mock_nessus_client.return_value = mock_nessus
    scan_ids = [1]
    previous_assessments = [{'scan_id': 1, 'vulns': [{'plugin_name': 'Test Vuln'}, {'plugin_name': 'Low Vuln'}]}]
    mock_nessus.scans.details.return_value = {'info': {'status': 'completed'}}
    results = verify_remediation(scan_ids, previous_assessments)
    assert results[1]['fixed'] == 1  # One vuln fixed (mock returns one vuln)

@patch('vuln_pipeline.ssm_client')
def test_get_param(mock_ssm, tmp_path):
    mock_ssm.return_value.get_parameter.side_effect = Exception("Parameter not found")
    (tmp_path / "nessus_config.toml").write_text(MOCK_NESSUS_CONFIG_TOML)
    assert get_param('url') == "https://mock-nessus:8834"
    with pytest.raises(ValueError):
        get_param('invalid_param')