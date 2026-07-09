#!/usr/bin/env python3
import yaml
import subprocess
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
import shutil
import uuid

def load_yaml(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def generate_tenant_init(config: Dict[str, Any]) -> str:
    num_tenants = config.get('num_tenants', 1)
    prefix = config.get('tenant_prefix', 'tenant_')
    role = config.get('app_user_role', 'MODIFY')
    tenant_config = config.get('tenant_config', {})
    keyspaces = tenant_config.get('keyspaces', [])

    cql = """
-- Initialize tenant keyspaces
"""
    for i in range(1, num_tenants + 1):
        ks = keyspaces[i-1] if i-1 < len(keyspaces) else {
            'name': f"{prefix}{i}",
            'replication': {'class': 'SimpleStrategy', 'replication_factor': 3},
            'tables': [{
                'name': 'data',
                'columns': [
                    {'name': 'id', 'type': 'uuid'},
                    {'name': 'value', 'type': 'text'}
                ],
                'partition_key': 'id',
                'initial_data': [{'table': 'data', 'rows': [{'id': str(uuid.uuid4()), 'value': f'sample_{i}'}]}]
            }]
        }
        tenant_keyspace = ks['name']
        replication = ks.get('replication', {'class': 'SimpleStrategy', 'replication_factor': 3})
        repl_str = f"{{ 'class': '{replication['class']}', 'replication_factor': {replication['replication_factor']} }}"
        cql += f"""
CREATE ROLE IF NOT EXISTS 'tenant_{i}_user' WITH PASSWORD = 'tenant_pass_{i}' AND LOGIN = true;
CREATE KEYSPACE IF NOT EXISTS {tenant_keyspace} WITH replication = {repl_str};
GRANT {role} ON KEYSPACE {tenant_keyspace} TO 'tenant_{i}_user';
"""
        for table in ks.get('tables', []):
            columns = ', '.join(f"{col['name']} {col['type']}" for col in table.get('columns', []))
            partition_key = table.get('partition_key')
            clustering_key = table.get('clustering_key', '')
            key_def = f"PRIMARY KEY ({partition_key}"
            if clustering_key:
                key_def += f", {clustering_key}"
            key_def += ")"
            cql += f"""
CREATE TABLE IF NOT EXISTS {tenant_keyspace}.{table['name']} ({columns}, {key_def});
"""
            for idx in table.get('indexes', []):
                cql += f"""
CREATE INDEX IF NOT EXISTS {idx['name']} ON {tenant_keyspace}.{table['name']} ({idx['column']});
"""
            for data in ks.get('initial_data', []):
                if data.get('table') == table['name']:
                    for row in data.get('rows', []):
                        row_str = ', '.join(f"'{v}'" if isinstance(v, str) and v != 'uuid()' else str(uuid.uuid4()) if v == 'uuid()' else str(v) for v in row.values())
                        cols = ', '.join(row.keys())
                        cql += f"""
INSERT INTO {tenant_keyspace}.{table['name']} ({cols}) VALUES ({row_str});
"""
    with open('tenant-init.cql', 'w') as f:
        f.write(cql)
    return 'tenant-init.cql'

def render_schema(schema_config_path: str, out_path: str = "schema/generated.cql") -> str:
    """Render CQL from a declarative schema config (schema/schema.yaml.example),
    applying per-table performance profiles. Requires jinja2; returns the path.
    """
    from jinja2 import Environment, FileSystemLoader

    cfg = load_yaml(schema_config_path)
    env = Environment(
        loader=FileSystemLoader("schema/templates"),
        trim_blocks=True, lstrip_blocks=True,
    )
    cql = env.get_template("schema.cql.j2").render(**cfg)
    with open(out_path, "w") as f:
        f.write(cql)
    print(f"Rendered schema -> {out_path}")
    return out_path


def deploy_kubernetes(config: Dict[str, Any]):
    if not check_command('kubectl'):
        print("Error: kubectl not installed.")
        sys.exit(1)
    cert_path = config.get('cert_path', './certs')
    namespace = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {'name': 'scylla'}
    }
    secret = {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {'name': 'scylla-secret', 'namespace': 'scylla'},
        'type': 'Opaque',
        'data': {
            'root-password': '<base64-encoded-password>',
            'tls-cert': '<base64-encoded-scylla.pem>',
            'tls-ca': '<base64-encoded-ca.pem>',
            'tls-cluster': '<base64-encoded-scylla-cluster.pem>'
        }
    }
    tenant_init_cm = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'name': 'scylla-tenant-init', 'namespace': 'scylla'},
        'data': {'tenant-init.cql': open('tenant-init.cql').read()}
    }
    scylla_cluster = {
        'apiVersion': 'scylla.scylladb.com/v1',
        'kind': 'ScyllaCluster',
        'metadata': {'name': 'scylla-cluster', 'namespace': 'scylla'},
        'spec': {
            'version': '5.4',
            'repository': 'scylladb/scylla-enterprise',
            'datacenter': {
                'name': 'dc1',
                'racks': [
                    {
                        'name': f'rack{i}',
                        'members': config.get('nodes_per_rack', 3),
                        'storage': {'capacity': f"{config.get('storage_gb', 100)}Gi"},
                        'resources': {'requests': {'cpu': '2', 'memory': '8Gi'}, 'limits': {'cpu': '8', 'memory': '12Gi'}},
                        'scyllaConfig': {
                            'smp': 8,
                            'memory': '12G',
                            'authenticator': 'PasswordAuthenticator',
                            'authorizer': 'CassandraAuthorizer'
                        }
                    } for i in range(config.get('num_racks', 2))
                ]
            },
            'securityContext': {'runAsUser': 999, 'runAsGroup': 999},
            'sysctl': ['fs.aio-max-nr=2097152'],
            'initContainers': [{
                'name': 'tenant-init',
                'image': config['image'],
                'command': ['/bin/sh', '-c', 'cqlsh --ssl -u $SCYLLA_ROOT_USERNAME -p $SCYLLA_ROOT_PASSWORD -f /docker-entrypoint-initdb.d/tenant-init.cql'],
                'env': [
                    {'name': 'SCYLLA_ROOT_USERNAME', 'value': config['root_username']},
                    {'name': 'SCYLLA_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': 'scylla-secret', 'key': 'root-password'}}}
                ],
                'volumeMounts': [{'name': 'initdb', 'mountPath': '/docker-entrypoint-initdb.d'}]
            }],
            'volumes': [
                {'name': 'initdb', 'configMap': {'name': 'scylla-tenant-init', 'items': [{'key': 'tenant-init.cql', 'path': 'tenant-init.cql'}]}},
                {'name': 'tls', 'secret': {'secretName': 'scylla-secret', 'items': [
                    {'key': 'tls-cert', 'path': 'scylla.pem'},
                    {'key': 'tls-ca', 'path': 'ca.pem'},
                    {'key': 'tls-cluster', 'path': 'scylla-cluster.pem'}
                ]}} if config.get('tls_enabled', True) else {}
            ],
            'networkPolicy': {
                'enabled': True,
                'ingress': [{'ports': [{'port': 9042}, {'port': 9142}, {'port': 7001}, {'port': 10001}]}]
            },
            'enterprise': {
                'auditLog': {
                    'enabled': True,
                    'categories': ['AUTH', 'DDL'],
                    'output': 'files:/var/log/scylla/audit'
                }
            }
        }
    }
    service = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {'name': 'scylla-cluster', 'namespace': 'scylla'},
        'spec': {
            'ports': [
                {'port': 9042, 'targetPort': 9042, 'name': 'cql'},
                {'port': 9142, 'targetPort': 9142, 'name': 'cql-ssl'} if config.get('tls_enabled', True) else {},
                {'port': 10001, 'targetPort': 10001, 'name': 'manager'},
                {'port': 7001, 'targetPort': 7001, 'name': 'internode'}
            ],
            'selector': {'scylla/cluster': 'scylla-cluster'}
        }
    }
    hpa = {
        'apiVersion': 'autoscaling/v2',
        'kind': 'HorizontalPodAutoscaler',
        'metadata': {'name': 'scylla-cluster-hpa', 'namespace': 'scylla'},
        'spec': {
            'scaleTargetRef': {'apiVersion': 'scylla.scylladb.com/v1', 'kind': 'ScyllaCluster', 'name': 'scylla-cluster'},
            'minReplicas': 3,
            'maxReplicas': 12,
            'metrics': [{'type': 'Resource', 'resource': {'name': 'cpu', 'target': {'type': 'Utilization', 'averageUtilization': 70}}}]
        }
    }
    manifests = [namespace, secret, tenant_init_cm, scylla_cluster, service, hpa]
    manifests = [m for m in manifests if m]  # Remove empty entries

    with open('k8s-scylladb.yaml', 'w') as f:
        yaml.dump_all(manifests, f, default_flow_style=False)
    subprocess.run(['kubectl', 'apply', '-f', 'k8s-scylladb.yaml'], check=True)
    print(f"ScyllaDB cluster deployed: {config['num_racks']} racks, {config['num_tenants']} tenants.")

def deploy_docker(config: Dict[str, Any]):
    if not check_command('docker') and not check_command('podman'):
        print("Error: Docker or Podman not installed.")
        sys.exit(1)
    generate_tenant_init(config)
    cmd = ['docker', 'compose', '-f', 'docker-compose.yml', 'up', '-d'] if check_command('docker') else ['podman-compose', 'up', '-d']
    subprocess.run(cmd, check=True)
    print("Docker/Podman deployment complete. Verify: cqlsh --ssl -u admin -p <pass> localhost 9142")

def deploy_ansible(config: Dict[str, Any], db_type: str):
    if not check_command('ansible-playbook'):
        print("Error: Ansible not installed.")
        sys.exit(1)
    password = os.getenv('SCYLLA_PASSWORD', config['root_password'])
    extra_vars = f"db_type={db_type} vault_scylla_password={password} image={config['image']} data_path={config['data_path']} num_racks={config.get('num_racks', 2)} nodes_per_rack={config.get('nodes_per_rack', 3)} num_tenants={config.get('num_tenants', 1)} cert_path={config.get('cert_path', './certs')} ca_cn=\"{config.get('ca_cn', 'ScyllaDB CA')}\" node_cn=\"{config.get('node_cn', 'ScyllaDB Node')}\" cluster_cn=\"{config.get('cluster_cn', 'ScyllaDB Cluster')}\" san=\"{config.get('san', 'dns:localhost,ip:127.0.0.1')}\" cert_days={config.get('cert_days', 365)} tls_enabled={str(config.get('tls_enabled', True)).lower()}"
    cmd = [
        'ansible-playbook', '-i', 'ansible/inventory.ini',
        f'ansible/playbooks/deploy-{db_type}.yml',
        '--extra-vars', extra_vars
    ]
    if not os.getenv('ANSIBLE_VAULT_PASSWORD_FILE'):
        cmd.append('--ask-vault-pass')
    subprocess.run(cmd, check=True)
    print("Ansible deployment complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy ScyllaDB.")
    parser.add_argument('config_file', help='Path to user_config.yaml')
    parser.add_argument('--schema', help='Render CQL from a declarative schema config (e.g. schema/schema.yaml.example) and exit')
    args = parser.parse_args()

    if args.schema:
        render_schema(args.schema)
        sys.exit(0)

    config = load_yaml(args.config_file)
    platform = config.get('platform', 'docker')
    db_type = config.get('db_type', 'enterprise-sharded')

    if db_type == 'enterprise-sharded':
        generate_tenant_init(config)
    if platform == 'kubernetes':
        deploy_kubernetes(config)
    elif platform in ['docker', 'podman']:
        deploy_docker(config)
    elif platform == 'ansible':
        deploy_ansible(config, db_type)
    else:
        print(f"Unsupported platform: {platform}")
        sys.exit(1)

    print("Deployment successful! Verify: cqlsh --ssl -u admin -p <pass> scylla-cluster.scylla.svc.cluster.local 9142")