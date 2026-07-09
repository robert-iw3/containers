# MongoDB

## Overview
Deploys MongoDB 8.0 (Enterprise) as a sharded cluster on Kubernetes, Docker, Podman, or Ansible. Supports multi-tenancy (100s of DBs), CIS hardening (auth, TLS, audit), and scaling (10+ shards, HPA). Configurable via `user_config.yaml`.

## Prerequisites
- Docker/Podman, kubectl, or Ansible installed.
- MongoDB Enterprise image built (`mongodb:8.0-enterprise`).
- TLS certs (`mongodb.pem`, `ca.pem`, `mongodb-cluster.pem`) and keyfile (`chmod 400`).

## Deployment
1. **Prepare Secrets**:
   - Keyfile: `openssl rand -base64 756 > keyfile && chmod 400 keyfile`
   - TLS certs: Use cert-manager or `openssl` for `mongodb.pem`, `ca.pem`, `mongodb-cluster.pem`.
   - Base64 encode: `base64 keyfile`, `echo -n 'changeme' | base64`, etc.

2. **Configure**:
   - Edit `user_config.yaml`:
     - Set `platform` (kubernetes, docker, podman, ansible).
     - Set `db_type: enterprise-sharded`, `num_shards: 10`, `num_tenants: 100`.
     - Customize `tenant_config` (collections, indexes, initial data).
   - Example:
     ```yaml
     num_tenants: 100
     tenant_config:
       collections:
         - name: data
           options: { timeseries: { timeField: timestamp } }
           indexes: [ { key: tenant_id, type: hashed } ]
           initial_data: [ { tenant_id: "tenant_{i}", status: "active" } ]
     ```

3. **Build Image**:
   ```bash
   docker build -t mongodb:8.0-enterprise .
   ```

4. **Deploy**:
   - Run: `python3 deploy_mongodb.py user_config.yaml`
   - For Kubernetes: `kubectl apply -f k8s-mongodb.yaml`
   - For Ansible: `ansible-playbook -i ansible/inventory.ini ansible/playbooks/deploy-enterprise-sharded.yml --ask-vault-pass`

5. **Initialize Cluster** (Kubernetes):
   - Configsvr: `kubectl exec -it mongodb-configsvr-0 -n mongodb -- mongosh --eval "rs.initiate()"`
   - Shards: `kubectl exec -it mongodb-shard0-0 -n mongodb -- mongosh --eval "rs.initiate()"`
   - Add shards: `kubectl exec -it mongodb-mongos-0 -n mongodb -- mongosh --eval "sh.addShard('shard0/mongodb-shard0-0.mongodb-shard0.mongodb.svc.cluster.local:27017')"`
   - Repeat for each shard (1 to `num_shards`).

6. **Verify**:
   - Connect: `mongosh --tls -u admin -p <pass> mongodb-mongos.mongodb.svc.cluster.local:27017/admin`
   - Check tenants: `show databases` (`tenant_1` to `tenant_100`). Verify: `use tenant_1; show collections; db.data.find()`.

## Multi-Tenancy
- Configure `num_tenants` and `tenant_config` in `user_config.yaml`.
- Creates DBs (`tenant_1` to `tenant_N`), users (`app_user_1`, RBAC), collections (`data`, `logs`), indexes (`hashed` for sharding), and initial data.
- Example: 100 DBs, each with `data` (timeseries), `logs`, and `tenant_id` index.

## Scaling
- Update `num_shards` or `num_tenants` in `user_config.yaml`, re-run Python.
- Mongos scales via HPA (3-10 replicas, 70% CPU).

## Security (CIS)
- Auth enabled, TLS required, audit sampled (5% overhead), JS disabled, non-root (UID 999), perms (750/400).
- Use Vault for passwords in prod.

## Notes
- Monitor: Add Prometheus exporter.
- Backup: Use mongodump or VolumeSnapshots.
- Test: Start with `num_tenants=10` in minikube.
- Install Ansible collections: `ansible-galaxy collection install kubernetes.core containers.podman`