import pytest
import subprocess
import os
import glob
import yaml
from kube_bench_orchestrator import KubeBenchOrchestrator

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
        'kubeconfig_path': str(tmp_path / 'kubeconfig'),
        'extra_args': ['--benchmark', 'cis-1.8']
    }
    config_path = tmp_path / 'config.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(config_content, f)
    with open(tmp_path / 'kubeconfig', 'w') as f:
        f.write('fake_kubeconfig')
    return str(config_path)

@pytest.mark.integration
def test_docker_integration(sample_config, tmp_path):
    # Skip if Docker is not available
    if subprocess.run(['docker', '--version'], capture_output=True).returncode != 0:
        pytest.skip("Docker not installed")

    # Build a minimal image for testing
    dockerfile = tmp_path / 'Dockerfile.test'
    with open(dockerfile, 'w') as f:
        f.write("""
FROM alpine:3.24
RUN echo '{"checks": [{"id": "1.1.1", "status": "PASS", "description": "Test check"}]}' > /output.json
CMD ["cat", "/output.json"]
""")
    subprocess.run(['docker', 'build', '-t', 'test-kube-bench:latest', '-f', str(dockerfile), str(tmp_path)], check=True)

    orchestrator = KubeBenchOrchestrator(sample_config)
    orchestrator.deployment_type = 'docker'
    result = orchestrator.run_scan({'endpoint': 'cluster1.example.com', 'timeout': 300})
    assert result['returncode'] == 0
    assert 'PASS' in result['stdout']
    assert glob.glob(os.path.join(orchestrator.reports_dir, 'kube_bench_cluster1.example.com_*'))

@pytest.mark.integration
def test_podman_integration(sample_config, tmp_path):
    # Skip if Podman is not available
    if subprocess.run(['podman', '--version'], capture_output=True).returncode != 0:
        pytest.skip("Podman not installed")

    # Build a minimal image for testing
    dockerfile = tmp_path / 'Dockerfile.test'
    with open(dockerfile, 'w') as f:
        f.write("""
FROM alpine:3.24
RUN echo '{"checks": [{"id": "1.1.1", "status": "PASS", "description": "Test check"}]}' > /output.json
CMD ["cat", "/output.json"]
""")
    subprocess.run(['podman', 'build', '-t', 'test-kube-bench:latest', '-f', str(dockerfile), str(tmp_path)], check=True)

    orchestrator = KubeBenchOrchestrator(sample_config)
    orchestrator.deployment_type = 'podman'
    result = orchestrator.run_scan({'endpoint': 'cluster1.example.com', 'timeout': 300})
    assert result['returncode'] == 0
    assert 'PASS' in result['stdout']
    assert glob.glob(os.path.join(orchestrator.reports_dir, 'kube_bench_cluster1.example.com_*'))

@pytest.mark.integration
def test_ansible_playbook(tmp_path):
    # Skip if Ansible is not available
    if subprocess.run(['ansible', '--version'], capture_output=True).returncode != 0:
        pytest.skip("Ansible not installed")

    inventory = tmp_path / 'inventory.yml'
    with open(inventory, 'w') as f:
        f.write("""
all:
  hosts:
    localhost:
      ansible_connection: local
""")

    playbook = tmp_path / 'playbook.yml'
    with open(playbook, 'w') as f:
        f.write("""
- name: Test playbook
  hosts: all
  become: yes
  roles:
    - kube_bench
""")

    config = tmp_path / 'config.yaml'
    with open(config, 'w') as f:
        yaml.dump({
            'endpoint_configs': [{'endpoint': 'cluster1.example.com', 'timeout': 300}],
            'reports_dir': str(tmp_path / 'reports'),
            'log_file': str(tmp_path / 'kube_bench_scan.log'),
            'deployment_type': 'docker',
            'max_concurrent_scans': 2,
            'report_formats': ['txt'],
            'timeout': 300,
            'kubectl_path': '/usr/local/bin/kubectl',
            'kubeconfig_path': str(tmp_path / 'kubeconfig'),
            'extra_args': ['--benchmark', 'cis-1.8']
        }, f)

    role_dir = tmp_path / 'roles' / 'kube_bench' / 'tasks'
    os.makedirs(role_dir, exist_ok=True)
    with open(role_dir / 'main.yml', 'w') as f:
        f.write("""
- name: Ensure reports directory exists
  file:
    path: "{{ kube_bench_reports_dir }}"
    state: directory
    mode: '0750'
    owner: "{{ ansible_user | default('nobody') }}"
""")

    result = subprocess.run(
        ['ansible-playbook', '-i', str(inventory), str(playbook)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert os.path.exists(tmp_path / 'reports')