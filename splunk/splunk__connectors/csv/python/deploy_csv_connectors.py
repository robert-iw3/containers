import os
import yaml
import subprocess
import argparse
import shutil
from datetime import datetime
from pydantic import BaseModel, validator
import psutil

class CSVConnectorsConfig(BaseModel):
    log_dir: str
    schemas_file: str

class SplunkConfig(BaseModel):
    enabled: bool
    hec_url: str
    hec_token: str

class ElasticsearchConfig(BaseModel):
    enabled: bool
    host: str
    index: str

class KubernetesConfig(BaseModel):
    replicas: int
    storage_class: str
    log_storage_size: str

class DeploymentConfig(BaseModel):
    method: str
    namespace: str
    kubernetes: KubernetesConfig

class Config(BaseModel):
    csv_connectors: CSVConnectorsConfig
    splunk: SplunkConfig
    elasticsearch: ElasticsearchConfig
    deployment: DeploymentConfig
    buffer_timeout: float
    worker_count: int
    batch_size: int
    delimiter: str

    @validator('worker_count')
    def validate_worker_count(cls, v):
        cpu_count = os.cpu_count() or 4
        if v > cpu_count * 2:
            raise ValueError(f"worker_count ({v}) exceeds twice the CPU count ({cpu_count})")
        return v

    @validator('deployment')
    def validate_deployment_method(cls, v):
        if v.method not in ['docker', 'podman', 'kubernetes', 'ansible']:
            raise ValueError(f"Invalid deployment method: {v.method}")
        return v

def validate_resources():
    cpu_count = os.cpu_count() or 4
    mem_total = psutil.virtual_memory().total / (1024 ** 3)  # GB
    disk_free = psutil.disk_usage('/').free / (1024 ** 3)  # GB
    if cpu_count < 2:
        print("Warning: Less than 2 CPU cores available")
    if mem_total < 2:
        print("Warning: Less than 2GB memory available")
    if disk_free < 2:
        print("Warning: Less than 2GB disk space available")

def backup_files(config_files, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    for src in config_files:
        if os.path.exists(src):
            dst = os.path.join(backup_dir, os.path.basename(src))
            shutil.copy2(src, dst)

def deploy_docker(config, use_podman=False):
    compose_cmd = 'podman-compose' if use_podman else 'docker-compose'
    if shutil.which(compose_cmd) is None:
        raise RuntimeError(f"{compose_cmd} not found")

    env = os.environ.copy()
    env.update({
        'CSV_LOG_DIR': config.csv_connectors.log_dir,
        'SCHEMAS_FILE': config.csv_connectors.schemas_file,
        'SPLUNK_ENABLED': str(config.splunk.enabled).lower(),
        'SPLUNK_HEC_URL': config.splunk.hec_url,
        'SPLUNK_TOKEN': config.splunk.hec_token,
        'ES_ENABLED': str(config.elasticsearch.enabled).lower(),
        'ES_HOST': config.elasticsearch.host,
        'ES_INDEX': config.elasticsearch.index,
        'BATCH_SIZE': str(config.batch_size),
        'BUFFER_TIMEOUT': str(config.buffer_timeout),
        'WORKER_COUNT': str(config.worker_count),
        'CSV_DELIMITER': config.delimiter
    })

    subprocess.run([compose_cmd, 'up', '-d', '--build'], env=env, check=True)

def deploy_kubernetes(config):
    if shutil.which('kubectl') is None:
        raise RuntimeError("kubectl not found")

    manifests = ['csv-pvc.yaml', 'csv-splunk-deployment.yaml', 'csv-elasticsearch-deployment.yaml']
    for manifest in manifests:
        with open(manifest, 'r') as f:
            content = f.read()
            content = content.replace('{{namespace}}', config.deployment.namespace)
            content = content.replace('{{replicas}}', str(config.deployment.kubernetes.replicas))
            content = content.replace('{{storage_class}}', config.deployment.kubernetes.storage_class)
            content = content.replace('{{log_storage_size}}', config.deployment.kubernetes.log_storage_size)
            content = content.replace('{{splunk_hec_url}}', config.splunk.hec_url)
            content = content.replace('{{splunk_token}}', config.splunk.hec_token)
            content = content.replace('{{es_host}}', config.elasticsearch.host)
            content = content.replace('{{es_index}}', config.elasticsearch.index)
            content = content.replace('{{batch_size}}', str(config.batch_size))
            content = content.replace('{{buffer_timeout}}', str(config.buffer_timeout))
            content = content.replace('{{worker_count}}', str(config.worker_count))
            content = content.replace('{{delimiter}}', config.delimiter)
            with open(f"temp_{manifest}", 'w') as f_temp:
                f_temp.write(content)

    for manifest in manifests:
        subprocess.run(['kubectl', 'apply', '-f', f"temp_{manifest}"], check=True)
        os.remove(f"temp_{manifest}")

def deploy_ansible(config):
    if shutil.which('ansible-playbook') is None:
        raise RuntimeError("ansible-playbook not found")

    subprocess.run(['ansible-playbook', 'deploy_csv_connectors.yml', '-e', f"config_file={os.path.abspath('deploy_config.yaml')}"], check=True)

def cleanup_docker(use_podman=False):
    compose_cmd = 'podman-compose' if use_podman else 'docker-compose'
    if shutil.which(compose_cmd):
        subprocess.run([compose_cmd, 'down', '-v'], check=True)

def cleanup_kubernetes(config):
    if shutil.which('kubectl'):
        manifests = ['csv-pvc.yaml', 'csv-splunk-deployment.yaml', 'csv-elasticsearch-deployment.yaml']
        for manifest in manifests:
            subprocess.run(['kubectl', 'delete', '-f', manifest, '-n', config.deployment.namespace], check=False)

def main():
    parser = argparse.ArgumentParser(description='Deploy CSV connectors for Splunk and Elasticsearch')
    parser.add_argument('--config', default='deploy_config.yaml', help='Path to configuration file')
    parser.add_argument('--cleanup', action='store_true', help='Cleanup deployment')
    args = parser.parse_args()

    config_files = [
        'deploy_config.yaml',
        'docker-compose.yml',
        'Dockerfile.connector',
        'schemas.yaml',
        'csv_splunk_connector.py',
        'csv_elasticsearch_connector.py',
        'csv-splunk-deployment.yaml',
        'csv-elasticsearch-deployment.yaml',
        'csv-pvc.yaml',
        'deploy_csv_connectors.yml'
    ]

    if args.cleanup:
        print("Cleaning up CSV connectors deployment...")
        config = load_config(args.config)
        if config.deployment.method == 'docker':
            cleanup_docker()
        elif config.deployment.method == 'podman':
            cleanup_docker(use_podman=True)
        elif config.deployment.method == 'kubernetes':
            cleanup_kubernetes(config)
        elif config.deployment.method == 'ansible':
            deploy_ansible(config)
        return

    validate_resources()
    config = load_config(args.config)
    backup_dir = f"backup/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_files(config_files, backup_dir)

    if config.deployment.method == 'docker':
        deploy_docker(config)
    elif config.deployment.method == 'podman':
        deploy_docker(config, use_podman=True)
    elif config.deployment.method == 'kubernetes':
        deploy_kubernetes(config)
    elif config.deployment.method == 'ansible':
        deploy_ansible(config)
    else:
        raise ValueError(f"Unsupported deployment method: {config.deployment.method}")

    print(f"CSV connectors deployed with log directory {config.csv_connectors.log_dir}")

def load_config(config_file):
    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)
    return Config(**config_data)

if __name__ == "__main__":
    main()