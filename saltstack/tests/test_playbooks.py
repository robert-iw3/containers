import pytest
import subprocess
import os

def test_ansible_playbook_syntax():
    playbooks = ['playbooks/deploy_docker.yml', 'playbooks/deploy_podman.yml', 'playbooks/deploy_kubernetes.yml', 'playbooks/backup.yml']
    for playbook in playbooks:
        result = subprocess.run(f"ansible-playbook {playbook} --syntax-check", shell=True, capture_output=True, text=True)
        assert result.returncode == 0, f"Syntax check failed for {playbook}: {result.stderr}"