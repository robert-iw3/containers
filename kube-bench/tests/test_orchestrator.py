import pytest
import os
import glob
import yaml
import subprocess
import json
import hmac
import hashlib
import xml.etree.ElementTree as ET
from unittest.mock import patch, mock_open
from kube_bench_orchestrator import KubeBenchOrchestrator, KubeBenchError

@pytest.fixture
def sample_config(tmp_path):
    config_content = {
        'endpoint_configs': [
            {'endpoint': 'cluster1.example.com', 'timeout': 300}
        ],
        'reports_dir': str(tmp_path / 'reports'),
        'log_file': str(tmp_path / 'kube_bench_scan.log'),
        'deployment_type': 'docker',
        'max_concurrent_scans': 2,
        'report_formats': ['txt', 'json', 'xml', 'html'],
        'timeout': 300,
        'kubectl_path': '/usr/local/bin/kubectl',
        'kubeconfig_path': '~/.kube/config',
        'extra_args': ['--benchmark', 'cis-1.8']
    }
    config_path = tmp_path / 'config.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(config_content, f)
    return str(config_path)

def test_load_config_valid(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    assert orchestrator.config['endpoint_configs'][0]['endpoint'] == 'cluster1.example.com'
    assert orchestrator.deployment_type == 'docker'
    assert orchestrator.log_file.endswith('kube_bench_scan.log')

def test_load_config_invalid(tmp_path):
    config_path = tmp_path / 'invalid.yaml'
    with open(config_path, 'w') as f:
        f.write("invalid: yaml: content")
    with pytest.raises(KubeBenchError, match="Configuration error"):
        KubeBenchOrchestrator(str(config_path))

def test_load_config_missing_fields(tmp_path):
    config_content = {'endpoint_configs': [{'endpoint': 'cluster1.example.com'}]}
    config_path = tmp_path / 'missing.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(config_content, f)
    with pytest.raises(KubeBenchError, match="Missing required config field"):
        KubeBenchOrchestrator(str(config_path))

def test_load_config_invalid_format(tmp_path):
    config_content = {
        'endpoint_configs': [{'endpoint': 'cluster1.example.com'}],
        'reports_dir': '/tmp/reports',
        'log_file': '/tmp/log.log',
        'deployment_type': 'docker',
        'report_formats': ['invalid']
    }
    config_path = tmp_path / 'invalid_format.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(config_content, f)
    with pytest.raises(KubeBenchError, match="Invalid report format"):
        KubeBenchOrchestrator(str(config_path))

def test_sanitize_path_valid(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    path = orchestrator.sanitize_path("/tmp/test-reports")
    assert path == os.path.abspath("/tmp/test-reports")

def test_sanitize_path_expands_home(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    path = orchestrator.sanitize_path("~/.kube/config")
    assert path == os.path.abspath(os.path.expanduser("~/.kube/config"))

def test_sanitize_path_invalid(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    with pytest.raises(KubeBenchError, match="Invalid characters in path"):
        orchestrator.sanitize_path("/tmp/test/../../etc/passwd")

def test_validate_endpoint_valid(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    orchestrator.validate_endpoint("cluster1.example.com")  # Should not raise

def test_validate_endpoint_invalid(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    with pytest.raises(KubeBenchError, match="Invalid endpoint"):
        orchestrator.validate_endpoint("cluster1;rm -rf /")

@patch('subprocess.run')
def test_run_scan_success(mock_run, sample_config, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess(
        args=['docker', 'run'], returncode=0, stdout='{"checks": [{"id": "1.1.1", "status": "PASS"}]}', stderr=''
    )
    orchestrator = KubeBenchOrchestrator(sample_config)
    result = orchestrator.run_scan({'endpoint': 'cluster1.example.com', 'timeout': 300})
    assert result['returncode'] == 0
    assert result['stdout'] == '{"checks": [{"id": "1.1.1", "status": "PASS"}]}'
    assert glob.glob(os.path.join(orchestrator.reports_dir, 'kube_bench_cluster1.example.com_*'))

@patch('subprocess.run')
def test_run_scan_timeout(mock_run, sample_config):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=['docker', 'run'], timeout=300)
    orchestrator = KubeBenchOrchestrator(sample_config)
    result = orchestrator.run_scan({'endpoint': 'cluster1.example.com', 'timeout': 300})
    assert result is None

def test_generate_report_txt(sample_config, tmp_path):
    orchestrator = KubeBenchOrchestrator(sample_config)
    report_path = orchestrator.generate_report("test output", "cluster1.example.com", "txt")
    assert os.path.exists(report_path)
    with open(report_path, 'r') as f:
        assert f.read() == "test output"
    assert oct(os.stat(report_path).st_mode & 0o777) == '0o640'

def test_generate_report_json(sample_config, tmp_path):
    orchestrator = KubeBenchOrchestrator(sample_config)
    report_path = orchestrator.generate_report('{"result": "pass"}', "cluster1.example.com", "json")
    assert os.path.exists(report_path)
    with open(report_path, 'r') as f:
        assert json.load(f) == {"result": "pass"}
    assert oct(os.stat(report_path).st_mode & 0o777) == '0o640'

def test_generate_report_xml(sample_config, tmp_path):
    orchestrator = KubeBenchOrchestrator(sample_config)
    report_path = orchestrator.generate_report("test output", "cluster1.example.com", "xml")
    assert os.path.exists(report_path)
    tree = ET.parse(report_path)
    assert tree.getroot().text == "test output"
    assert oct(os.stat(report_path).st_mode & 0o777) == '0o640'

def test_generate_report_html(sample_config, tmp_path):
    orchestrator = KubeBenchOrchestrator(sample_config)
    output = '{"checks": [{"id": "1.1.1", "status": "PASS", "description": "Test check"}]}'
    report_path = orchestrator.generate_report(output, "cluster1.example.com", "html")
    assert os.path.exists(report_path)
    with open(report_path, 'r') as f:
        content = f.read()
        assert "Kube-bench Report - cluster1.example.com" in content
        assert '<td class="pass">PASS</td>' in content
    assert oct(os.stat(report_path).st_mode & 0o777) == '0o640'

def test_generate_aggregate_report(sample_config, tmp_path):
    orchestrator = KubeBenchOrchestrator(sample_config)
    results = [
        {'endpoint': 'cluster1.example.com', 'returncode': 0, 'stdout': '{"result": "pass"}', 'stderr': ''},
        {'endpoint': 'cluster2.example.com', 'returncode': 1, 'stdout': '', 'stderr': 'error'}
    ]
    report_path = orchestrator.generate_aggregate_report(results)
    assert os.path.exists(report_path)
    with open(report_path, 'r') as f:
        summary = json.load(f)
        assert summary['total_endpoints'] == 2
        assert summary['successful'] == 1
        assert summary['failed'] == 1
    assert oct(os.stat(report_path).st_mode & 0o777) == '0o640'

def test_verify_binary_signature_valid(sample_config, monkeypatch):
    monkeypatch.setenv('KUBE_BENCH_HMAC_KEY', 'test-hmac-key')
    orchestrator = KubeBenchOrchestrator(sample_config, binary_signature=hmac.new(b'test-hmac-key', b'test_binary', hashlib.sha256).hexdigest())
    with patch('builtins.open', new_callable=mock_open, read_data=b'test_binary'):
        orchestrator.verify_binary_signature('/usr/local/bin/kube-bench')  # Should not raise

def test_verify_binary_signature_invalid(sample_config, monkeypatch):
    monkeypatch.setenv('KUBE_BENCH_HMAC_KEY', 'test-hmac-key')
    orchestrator = KubeBenchOrchestrator(sample_config, binary_signature='invalid_signature')
    with patch('builtins.open', new_callable=mock_open, read_data=b'test_binary'):
        with pytest.raises(KubeBenchError, match="Binary signature verification failed"):
            orchestrator.verify_binary_signature('/usr/local/bin/kube-bench')

def test_verify_binary_signature_missing_key(sample_config, monkeypatch):
    monkeypatch.delenv('KUBE_BENCH_HMAC_KEY', raising=False)
    orchestrator = KubeBenchOrchestrator(sample_config, binary_signature='some_signature')
    with pytest.raises(KubeBenchError, match="KUBE_BENCH_HMAC_KEY is not set"):
        orchestrator.verify_binary_signature('/usr/local/bin/kube-bench')

def test_build_command_docker(sample_config):
    orchestrator = KubeBenchOrchestrator(sample_config)
    cmd = orchestrator.build_command("cluster1.example.com")
    assert cmd[0] == 'docker'
    assert '--security-opt' in cmd
    assert 'apparmor=kube_bench_profile' in cmd
    assert '-it' not in cmd
    assert '--benchmark' in cmd
    assert 'cis-1.8' in cmd

def test_build_command_podman(sample_config):
    with open(sample_config, 'r') as f:
        config = yaml.safe_load(f)
    config['deployment_type'] = 'podman'
    with open(sample_config, 'w') as f:
        yaml.dump(config, f)
    orchestrator = KubeBenchOrchestrator(sample_config)
    cmd = orchestrator.build_command("cluster1.example.com")
    assert cmd[0] == 'podman'
    assert '--selinux' in cmd
    assert 'label=type:kube_bench_t' in cmd
    assert '-it' not in cmd

def test_build_command_kubernetes(sample_config):
    with open(sample_config, 'r') as f:
        config = yaml.safe_load(f)
    config['deployment_type'] = 'kubernetes'
    with open(sample_config, 'w') as f:
        yaml.dump(config, f)
    orchestrator = KubeBenchOrchestrator(sample_config)
    cmd = orchestrator.build_command("cluster1.example.com")
    assert cmd[0] == 'kubectl'
    assert 'apply' in cmd
    assert '--benchmark' in cmd