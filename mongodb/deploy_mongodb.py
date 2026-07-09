#!/usr/bin/env python3
import yaml
import subprocess
import os
import sys
import argparse
import shutil
from pathlib import Path
from typing import Dict, Any
import json

def load_yaml(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"YAML error in {file_path}: {e}")
        sys.exit(1)

def merge_configs(base: Dict[str, Any], cis: Dict[str, Any], specific: Dict[str, Any], ram_gb: float) -> Dict[str, Any]:
    merged = base.copy()
    merged.update(cis)
    merged.update(specific)
    if 'storage' in merged and 'wiredTiger' in merged['storage'] and 'engineConfig' in merged['storage']['wiredTiger']:
        merged['storage']['wiredTiger']['engineConfig']['cacheSizeGB'] = max(0.25, ram_gb * 0.6 - 0.5)
    return merged

def check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def generate_tenant_init(config: Dict[str, Any]) -> str:
    num_tenants = config.get('num_tenants', 100)
    prefix = config.get('tenant_prefix', 'tenant_')
    role = config.get('app_user_role', 'readWrite')
    tenant_config = config.get('tenant_config', {})
    collections = tenant_config.get('collections', [])

    js = f"""
    var numTenants = {num_tenants};
    var prefix = '{prefix}';
    var role = '{role}';
    for (var i = 1; i <= numTenants; i++) {{
      var dbName = prefix + i;
      var user = 'app_user_' + i;
      var pwd = 'tenant_pass_' + i;  // In prod: Use secrets
      db.getSiblingDB('admin').createRole({{
        role: 'tenantRole_' + i,
        privileges: [{{ resource: {{ db: dbName, collection: '' }}, actions: [role] }}],
        roles: []
      }});
      db.getSiblingDB(dbName).createUser({{
        user: user,
        pwd: pwd,
        roles: [{{ role: 'tenantRole_' + i, db: 'admin' }}]
      }});
      print('Tenant ' + dbName + ' provisioned with user ' + user);
    """
    for coll in collections:
        coll_name = coll.get('name', 'data')
        options = json.dumps(coll.get('options', {}), separators=(',', ':'))
        indexes = coll.get('indexes', [])
        initial_data = coll.get('initial_data', [])
        js += f"""
      db = db.getSiblingDB(dbName);
      db.createCollection('{coll_name}', {options});
        """
        for idx in indexes:
            key = idx.get('key')
            idx_type = idx.get('type', 1)
            js += f"""
      db.{coll_name}.createIndex({{ '{key}': {json.dumps(idx_type)} }});
            """
        for doc in initial_data:
            doc_str = json.dumps(doc).replace('{i}', "' + i + '")
            js += f"""
      db.{coll_name}.insertOne({doc_str});
            """
    js += """
    }
    """
    with open('tenant-init.js', 'w') as f:
        f.write(js)
    return 'tenant-init.js'

def deploy_docker(config: Dict[str, Any], merged_config_file: str):
    if not check_command('docker'):
        print("Error: Docker not installed.")
        sys.exit(1)
    cmd = [
        'docker', 'run', '-d',
        '--cpus=1', '--memory=2g',
        '--name', f'mongodb-{config["db_type"]}',
        '-p', '27017:27017',
        '-v', f"{config['data_path']}:/data/db",
        '-v', f"{merged_config_file}:/etc/mongod.conf:ro",
        '-v', f"{config['keyfile_path']}:/etc/mongod-keyfile:ro",
        '-v', f"{config['tls_cert_path']}:/etc/ssl/mongodb.pem:ro",
        '-v', f"{config['tls_ca_path']}:/etc/ssl/ca.pem:ro",
        '-v', f"{config['tls_cluster_path']}:/etc/ssl/mongodb-cluster.pem:ro",
        '-e', f'MONGO_INITDB_ROOT_USERNAME={config["root_username"]}',
        '-e', f'MONGO_INITDB_ROOT_PASSWORD={os.getenv("MONGO_PASSWORD", config["root_password"])}',
        '-e', f'MONGO_INITDB_REPLSET={config.get("init_replset", "")}',
        config['image'], '--config', '/etc/mongod.conf'
    ]
    subprocess.run(cmd, check=True)
    print("Docker deployment complete.")

def deploy_podman(config: Dict[str, Any], merged_config_file: str):
    if not check_command('podman'):
        print("Error: Podman not installed.")
        sys.exit(1)
    cmd = [
        'podman', 'run', '-d',
        '--cpus=1', '--memory=2g',
        '--name', f'mongodb-{config["db_type"]}',
        '-p', '27017:27017',
        '-v', f"{config['data_path']}:/data/db:Z",
        '-v', f"{merged_config_file}:/etc/mongod.conf:ro:Z",
        '-v', f"{config['keyfile_path']}:/etc/mongod-keyfile:ro:Z",
        '-v', f"{config['tls_cert_path']}:/etc/ssl/mongodb.pem:ro:Z",
        '-v', f"{config['tls_ca_path']}:/etc/ssl/ca.pem:ro:Z",
        '-v', f"{config['tls_cluster_path']}:/etc/ssl/mongodb-cluster.pem:ro:Z",
        '-e', f'MONGO_INITDB_ROOT_USERNAME={config["root_username"]}',
        '-e', f'MONGO_INITDB_ROOT_PASSWORD={os.getenv("MONGO_PASSWORD", config["root_password"])}',
        '-e', f'MONGO_INITDB_REPLSET={config.get("init_replset", "")}',
        config['image'], '--config', '/etc/mongod.conf'
    ]
    subprocess.run(cmd, check=True)
    print("Podman deployment complete.")

def deploy_kubernetes(config: Dict[str, Any], merged_config: Dict[str, Any]):
    if not check_command('kubectl'):
        print("Error: kubectl not installed.")
        sys.exit(1)
    namespace = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {'name': 'mongodb'}
    }
    secret = {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {'name': 'mongodb-secret', 'namespace': 'mongodb'},
        'type': 'Opaque',
        'data': {
            'keyfile': '<base64-encoded-keyfile-content>',
            'root-password': '<base64-encoded-password>',
            'tls-cert': '<base64-encoded-mongodb.pem>',
            'tls-ca': '<base64-encoded-ca.pem>',
            'tls-cluster': '<base64-encoded-mongodb-cluster.pem>'
        }
    }
    tenant_init_cm = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'name': 'mongodb-tenant-init', 'namespace': 'mongodb'},
        'data': {'tenant-init.js': open('tenant-init.js').read()}
    }
    manifests = [namespace, secret, tenant_init_cm]

    # Config Server
    configsvr_cm = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'name': 'mongodb-configsvr-config', 'namespace': 'mongodb'},
        'data': {'mongod.conf': yaml.dump(merged_config, default_flow_style=False)}
    }
    configsvr_service = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {'name': 'mongodb-configsvr', 'namespace': 'mongodb'},
        'spec': {
            'clusterIP': 'None',
            'ports': [{'port': 27019, 'targetPort': 27019}],
            'selector': {'app': 'mongodb-configsvr'}
        }
    }
    configsvr_statefulset = {
        'apiVersion': 'apps/v1',
        'kind': 'StatefulSet',
        'metadata': {'name': 'mongodb-configsvr', 'namespace': 'mongodb'},
        'spec': {
            'serviceName': 'mongodb-configsvr',
            'replicas': 3,
            'selector': {'matchLabels': {'app': 'mongodb-configsvr'}},
            'template': {
                'metadata': {'labels': {'app': 'mongodb-configsvr'}},
                'spec': {
                    'containers': [{
                        'name': 'mongodb',
                        'image': config['image'],
                        'ports': [{'containerPort': 27019}],
                        'volumeMounts': [
                            {'name': 'data', 'mountPath': '/data/configdb'},
                            {'name': 'config', 'mountPath': '/etc/mongod.conf', 'subPath': 'mongod.conf', 'readOnly': True},
                            {'name': 'keyfile', 'mountPath': '/etc/mongod-keyfile', 'readOnly': True},
                            {'name': 'tls', 'mountPath': '/etc/ssl', 'readOnly': True},
                            {'name': 'initdb', 'mountPath': '/docker-entrypoint-initdb.d', 'readOnly': True}
                        ],
                        'env': [
                            {'name': 'MONGO_INITDB_ROOT_USERNAME', 'value': config['root_username']},
                            {'name': 'MONGO_INITDB_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': 'mongodb-secret', 'key': 'root-password'}}},
                            {'name': 'MONGO_INITDB_REPLSET', 'value': config.get('init_replset', 'configReplSet')}
                        ],
                        'command': ['/usr/local/bin/docker-entrypoint.sh', 'mongod', '--config', '/etc/mongod.conf', '--configsvr'],
                        'resources': {'requests': {'cpu': '500m', 'memory': '1Gi'}, 'limits': {'cpu': '1', 'memory': '2Gi'}},
                        'securityContext': {'runAsUser': 999, 'runAsGroup': 999}
                    }],
                    'volumes': [
                        {'name': 'config', 'configMap': {'name': 'mongodb-configsvr-config', 'items': [{'key': 'mongod.conf', 'path': 'mongod.conf'}]}},
                        {'name': 'keyfile', 'secret': {'secretName': 'mongodb-secret', 'items': [{'key': 'keyfile', 'path': 'mongod-keyfile'}]}},
                        {'name': 'tls', 'secret': {'secretName': 'mongodb-secret', 'items': [
                            {'key': 'tls-cert', 'path': 'mongodb.pem'},
                            {'key': 'tls-ca', 'path': 'ca.pem'},
                            {'key': 'tls-cluster', 'path': 'mongodb-cluster.pem'}
                        ]}},
                        {'name': 'initdb', 'configMap': {'name': 'mongodb-tenant-init', 'items': [{'key': 'tenant-init.js', 'path': 'tenant-init.js'}]}}
                    ]
                }
            },
            'volumeClaimTemplates': [{
                'metadata': {'name': 'data'},
                'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': str(config.get('storage_gb', 100)) + 'Gi'}}}
            }]
        }
    }
    manifests.extend([configsvr_cm, configsvr_service, configsvr_statefulset])

    # Shards
    for shard in range(config.get('num_shards', 1)):
        shard_config = merged_config.copy()
        shard_config['sharding']['clusterRole'] = 'shardsvr'
        shard_config['replication']['replSetName'] = f'shard{shard}'
        shard_cm = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': f'mongodb-shard{shard}-config', 'namespace': 'mongodb'},
            'data': {'mongod.conf': yaml.dump(shard_config, default_flow_style=False)}
        }
        shard_service = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {'name': f'mongodb-shard{shard}', 'namespace': 'mongodb'},
            'spec': {
                'clusterIP': 'None',
                'ports': [{'port': 27017, 'targetPort': 27017}],
                'selector': {'app': f'mongodb-shard{shard}'}
            }
        }
        shard_statefulset = {
            'apiVersion': 'apps/v1',
            'kind': 'StatefulSet',
            'metadata': {'name': f'mongodb-shard{shard}', 'namespace': 'mongodb'},
            'spec': {
                'serviceName': f'mongodb-shard{shard}',
                'replicas': config.get('replicas_per_shard', 3),
                'selector': {'matchLabels': {'app': f'mongodb-shard{shard}'}},
                'template': {
                    'metadata': {'labels': {'app': f'mongodb-shard{shard}'}},
                    'spec': {
                        'containers': [{
                            'name': 'mongodb',
                            'image': config['image'],
                            'ports': [{'containerPort': 27017}],
                            'volumeMounts': [
                                {'name': 'data', 'mountPath': '/data/db'},
                                {'name': 'config', 'mountPath': '/etc/mongod.conf', 'subPath': 'mongod.conf', 'readOnly': True},
                                {'name': 'keyfile', 'mountPath': '/etc/mongod-keyfile', 'readOnly': True},
                                {'name': 'tls', 'mountPath': '/etc/ssl', 'readOnly': True},
                                {'name': 'initdb', 'mountPath': '/docker-entrypoint-initdb.d', 'readOnly': True}
                            ],
                            'env': [
                                {'name': 'MONGO_INITDB_ROOT_USERNAME', 'value': config['root_username']},
                                {'name': 'MONGO_INITDB_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': 'mongodb-secret', 'key': 'root-password'}}},
                                {'name': 'MONGO_INITDB_REPLSET', 'value': f'shard{shard}'}
                            ],
                            'command': ['/usr/local/bin/docker-entrypoint.sh', 'mongod', '--config', '/etc/mongod.conf', '--shardsvr'],
                            'resources': {'requests': {'cpu': '500m', 'memory': '1Gi'}, 'limits': {'cpu': '1', 'memory': '2Gi'}},
                            'securityContext': {'runAsUser': 999, 'runAsGroup': 999}
                        }],
                        'volumes': [
                            {'name': 'config', 'configMap': {'name': f'mongodb-shard{shard}-config', 'items': [{'key': 'mongod.conf', 'path': 'mongod.conf'}]}},
                            {'name': 'keyfile', 'secret': {'secretName': 'mongodb-secret', 'items': [{'key': 'keyfile', 'path': 'mongod-keyfile'}]}},
                            {'name': 'tls', 'secret': {'secretName': 'mongodb-secret', 'items': [
                                {'key': 'tls-cert', 'path': 'mongodb.pem'},
                                {'key': 'tls-ca', 'path': 'ca.pem'},
                                {'key': 'tls-cluster', 'path': 'mongodb-cluster.pem'}
                            ]}},
                            {'name': 'initdb', 'configMap': {'name': 'mongodb-tenant-init', 'items': [{'key': 'tenant-init.js', 'path': 'tenant-init.js'}]}}
                        ]
                    }
                },
                'volumeClaimTemplates': [{
                    'metadata': {'name': 'data'},
                    'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': str(config.get('storage_gb', 100)) + 'Gi'}}}
                }]
            }
        }
        manifests.extend([shard_cm, shard_service, shard_statefulset])

    # Mongos
    mongos_config = merged_config.copy()
    mongos_config['sharding']['clusterRole'] = 'mongos'
    mongos_config['sharding']['configDB'] = 'configReplSet/mongodb-configsvr-0.mongodb-configsvr.mongodb.svc.cluster.local:27019,mongodb-configsvr-1.mongodb-configsvr.mongodb.svc.cluster.local:27019,mongodb-configsvr-2.mongodb-configsvr.mongodb.svc.cluster.local:27019'
    mongos_cm = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'name': 'mongodb-mongos-config', 'namespace': 'mongodb'},
        'data': {'mongod.conf': yaml.dump(mongos_config, default_flow_style=False)}
    }
    mongos_service = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {'name': 'mongodb-mongos', 'namespace': 'mongodb'},
        'spec': {
            'ports': [{'port': 27017, 'targetPort': 27017}],
            'selector': {'app': 'mongos'}
        }
    }
    mongos_deployment = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'mongodb-mongos', 'namespace': 'mongodb'},
        'spec': {
            'replicas': 3,
            'selector': {'matchLabels': {'app': 'mongos'}},
            'template': {
                'metadata': {'labels': {'app': 'mongos'}},
                'spec': {
                    'containers': [{
                        'name': 'mongos',
                        'image': config['image'],
                        'ports': [{'containerPort': 27017}],
                        'volumeMounts': [
                            {'name': 'config', 'mountPath': '/etc/mongod.conf', 'subPath': 'mongod.conf', 'readOnly': True},
                            {'name': 'keyfile', 'mountPath': '/etc/mongod-keyfile', 'readOnly': True},
                            {'name': 'tls', 'mountPath': '/etc/ssl', 'readOnly': True}
                        ],
                        'env': [
                            {'name': 'MONGO_INITDB_ROOT_USERNAME', 'value': config['root_username']},
                            {'name': 'MONGO_INITDB_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': 'mongodb-secret', 'key': 'root-password'}}}
                        ],
                        'command': ['/usr/local/bin/docker-entrypoint.sh', 'mongos', '--config', '/etc/mongod.conf'],
                        'resources': {'requests': {'cpu': '500m', 'memory': '1Gi'}, 'limits': {'cpu': '1', 'memory': '2Gi'}},
                        'securityContext': {'runAsUser': 999, 'runAsGroup': 999}
                    }],
                    'volumes': [
                        {'name': 'config', 'configMap': {'name': 'mongodb-mongos-config', 'items': [{'key': 'mongod.conf', 'path': 'mongod.conf'}]}},
                        {'name': 'keyfile', 'secret': {'secretName': 'mongodb-secret', 'items': [{'key': 'keyfile', 'path': 'mongod-keyfile'}]}},
                        {'name': 'tls', 'secret': {'secretName': 'mongodb-secret', 'items': [
                            {'key': 'tls-cert', 'path': 'mongodb.pem'},
                            {'key': 'tls-ca', 'path': 'ca.pem'},
                            {'key': 'tls-cluster', 'path': 'mongodb-cluster.pem'}
                        ]}}
                    ]
                }
            }
        }
    }
    hpa = {
        'apiVersion': 'autoscaling/v2',
        'kind': 'HorizontalPodAutoscaler',
        'metadata': {'name': 'mongodb-mongos-hpa', 'namespace': 'mongodb'},
        'spec': {
            'scaleTargetRef': {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'name': 'mongodb-mongos'},
            'minReplicas': 3,
            'maxReplicas': 10,
            'metrics': [{'type': 'Resource', 'resource': {'name': 'cpu', 'target': {'type': 'Utilization', 'averageUtilization': 70}}}]
        }
    }
    manifests.extend([mongos_cm, mongos_service, mongos_deployment, hpa])

    with open('k8s-mongodb.yaml', 'w') as f:
        yaml.dump_all(manifests, f, default_flow_style=False)
    subprocess.run(['kubectl', 'apply', '-f', 'k8s-mongodb.yaml'], check=True)
    print(f"K8s sharded cluster deployed: {config['num_shards']} shards, {config['num_tenants']} tenants provisioned via init script.")

def deploy_ansible(config: Dict[str, Any], db_type: str):
    if not check_command('ansible-playbook'):
        print("Error: Ansible not installed.")
        sys.exit(1)
    password = os.getenv('MONGO_PASSWORD', config['root_password'])
    extra_vars = f"db_type={db_type} vault_mongo_password={password} image={config['image']} data_path={config['data_path']} keyfile_path={config['keyfile_path']} init_replset={config.get('init_replset', '')} num_shards={config.get('num_shards', 1)} num_tenants={config.get('num_tenants', 100)}"
    cmd = [
        'ansible-playbook', '-i', 'ansible/inventory.ini',
        f'ansible/playbooks/deploy-{db_type}.yml',
        '--extra-vars', extra_vars
    ]
    if not os.getenv('ANSIBLE_VAULT_PASSWORD_FILE') and not os.getenv('ANSIBLE_VAULT_PASSWORD'):
        cmd.append('--ask-vault-pass')
    subprocess.run(cmd, check=True)
    print("Ansible deployment complete. Use Vault for production secrets.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy MongoDB based on config.")
    parser.add_argument('config_file', help='Path to user_config.yaml')
    args = parser.parse_args()

    user_config = load_yaml(args.config_file)
    platform = user_config['platform']
    db_type = user_config['db_type']

    base_config = load_yaml('config/base.yaml')
    cis_config = load_yaml('config/cis-hardened.yaml')
    db_configs = {
        'standalone': load_yaml('config/standalone.yaml'),
        'replica': load_yaml('config/replica.yaml'),
        'sharded': load_yaml('config/sharded.yaml'),
        'enterprise-sharded': load_yaml('config/enterprise-sharded.yaml')
    }
    specific_config = db_configs.get(db_type, {})
    ram_gb = user_config.get('ram_gb', 4.0)
    merged_config = merge_configs(base_config, cis_config, specific_config, ram_gb)
    merged_file = Path('merged_mongod.conf')
    with open(merged_file, 'w') as f:
        yaml.dump(merged_config, f, default_flow_style=False)

    if db_type == 'enterprise-sharded':
        generate_tenant_init(user_config)
    if platform in ['docker', 'podman']:
        if platform == 'docker':
            deploy_docker(user_config, str(merged_file))
        else:
            deploy_podman(user_config, str(merged_file))
    elif platform == 'kubernetes':
        deploy_kubernetes(user_config, merged_config)
    elif platform == 'ansible':
        deploy_ansible(user_config, db_type)
    else:
        print(f"Unsupported platform: {platform}")
        sys.exit(1)

    merged_file.unlink()
    print("Deployment successful! For security, never commit passwords; use env/Vault. Verify: Connect via mongosh with auth.")