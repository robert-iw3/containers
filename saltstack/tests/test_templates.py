import pytest
import yaml
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

def test_render_docker_compose():
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('docker-compose.j2')
    context = {
        'salt_version': '3006.5',
        'image_registry': 'docker.io',
        'minion_count': 2,
        'master_key': 'secret-key',
        'enable_logging': True
    }
    rendered = template.render(**context)
    parsed = yaml.safe_load(rendered)
    assert parsed['services']['salt-master']['image'] == 'docker.io/saltstack/salt:3006.5'
    assert len(parsed['services']) == 3  # 1 master + 2 minions
    assert parsed['services']['salt-master']['logging']['driver'] == 'fluentd'

def test_render_k8s_deployment():
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('k8s-deployment.j2')
    context = {
        'salt_version': '3006.5',
        'image_registry': 'docker.io',
        'namespace': 'saltstack',
        'replicas': 2,
        'minion_count': 2,
        'master_key': 'secret-key'
    }
    rendered = template.render(**context)
    parsed = yaml.safe_load_all(rendered)
    deployments = list(parsed)
    assert deployments[0]['metadata']['name'] == 'salt-master'
    assert deployments[0]['spec']['replicas'] == 2
    assert deployments[1]['kind'] == 'PersistentVolumeClaim'