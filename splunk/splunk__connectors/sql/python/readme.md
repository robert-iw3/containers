# SQL Connector

## Prerequisites
- **Python**: 3.12+ with `pip`.
- **Container Runtime**: Docker or Podman with `docker-compose` or `podman-compose`.
- **Kubernetes**: `kubectl` for Kubernetes deployments.
- **Ansible**: `ansible-playbook` with `community.docker` collection.
- **Splunk**: HTTP Event Collector (HEC) configured.
- **Database**: Read access to tables/views; for PostgreSQL CDC, logical replication enabled (`wal_level=logical`).
- **System Resources**: 2GB memory, 2 CPU cores, 2GB disk space.
- **Dependencies**:
  ```bash
  pip install -r requirements.txt
  ansible-galaxy collection install community.docker
  ```

## File Structure
```
sql-connector/
├── src/
│   ├── main.py                    # Main entry point
│   ├── handler.py                # Database polling and CDC logic
│   ├── schema.py                 # Schema parsing logic
│   ├── sender.py                 # Splunk sender logic
├── requirements.txt               # Python dependencies
├── deploy_sql_connectors.py      # Deployment script
├── deploy_config.yaml            # Configuration file
├── schemas.yaml                  # Schema mappings
├── Dockerfile                    # Container build
├── docker-compose.yml            # Docker/Podman orchestration
├── sql-splunk-deployment.yaml    # Kubernetes manifest
├── deploy_sql_connectors.yml     # Ansible playbook
├── README.md                     # This file
├── backup/                      # Backup directory
```

## Deployment Steps

### 1. Prepare Files
Place all files in `sql-connector/`. Ensure database access and, for PostgreSQL CDC, logical replication (`wal_level=logical` in `postgresql.conf`, replication role).

### 2. Configure
Edit `deploy_config.yaml`:
```yaml
sql_connectors:
  schemas_file: '/app/schemas.yaml'
  state_path: '/app/state.db'
splunk:
  enabled: true
  hec_url: 'https://your-splunk-host:8088/services/collector/event'
  hec_token: 'your-splunk-hec-token'
database:
  db_type: 'postgres'
  conn_str: 'postgres://user:pass@host:port/dbname'
deployment:
  method: 'docker'
  namespace: 'sql-connectors'
  kubernetes:
    replicas: 1
buffer_timeout: 2.0
worker_count: 4
batch_size: 100
poll_interval: 60
cdc_enabled: false
max_connections_per_table: 5
metrics_port: 9000
```

Edit `schemas.yaml`:
```yaml
schemas:
  - name: network_events
    table_name: network_events_table
    timestamp_field: timestamp
    id_field: id
    mappings:
      cim:
        time: timestamp
        event_id: id
        source: source_ip
        # etc.
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Deploy
- **Docker**:
  ```bash
  docker-compose up -d --build
  ```
- **Podman**:
  ```bash
  podman-compose up -d --build
  ```
- **Kubernetes**:
  ```bash
  python3 deploy_sql_connectors.py --config deploy_config.yaml
  ```
- **Ansible**:
  ```bash
  ansible-playbook deploy_sql_connectors.yml -e "config_file=deploy_config.yaml"
  ```

### 5. Verify
- Containers: `docker ps` or `podman ps`
- Pods: `kubectl get pods -n sql-connectors`
- Splunk: `index=* source=sql:*`
- Metrics: `curl http://localhost:9000/metrics`
- Logs: `docker logs sql-splunk` or `kubectl logs -n sql-connectors -l app=sql-splunk`

## Configuration
- **Environment Variables**:
  - `SCHEMAS_FILE`, `STATE_PATH`, `SPLUNK_HEC_URL`, `SPLUNK_TOKEN`, `DB_TYPE`, `DB_CONN_STR`, `BATCH_SIZE`, `BUFFER_TIMEOUT`, `WORKER_COUNT`, `POLL_INTERVAL`, `CDC_ENABLED`, `MAX_CONNECTIONS_PER_TABLE`, `METRICS_PORT`, `PYTHON_LOGGING_LEVEL`.

## Production Considerations
- **Performance**: Handles large datasets with batching and per-table pools. Tune `BATCH_SIZE`, `POLL_INTERVAL`, `MAX_CONNECTIONS_PER_TABLE`.
- **Fault Tolerance**: Persistent state, retries, logging, graceful shutdown.
- **Security**: Use secrets for `DB_CONN_STR`, `SPLUNK_TOKEN`. Enable TLS in `conn_str`.
- **Monitoring**: Prometheus metrics at `/metrics`. Integrate with Grafana.
- **CDC**: Requires PostgreSQL logical replication setup.

## Cleanup
```bash
python3 deploy_sql_connectors.py --config deploy_config.yaml --cleanup
```
Ansible:
```bash
ansible-playbook deploy_sql_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting
- **Connection Issues**: Verify `DB_CONN_STR`, network, permissions.
- **CDC Errors**: Ensure PostgreSQL `wal_level=logical`, replication role.
- **Performance**: Adjust `BATCH_SIZE`, `POLL_INTERVAL`, `MAX_CONNECTIONS_PER_TABLE`.
- **Logs**: Set `PYTHON_LOGGING_LEVEL=DEBUG`.

## Validation and Error Checking
- **Syntax**: Python files pass `flake8` and run with Python 3.12. YAML files are valid.
- **Dependencies**: All required in `requirements.txt`, compatible with Python 3.12.
- **Interoperability**: Supports all DB types, deployment methods. CDC is Postgres-only.
- **Error Handling**: Custom exceptions, retries with `tenacity`, structured logging with `structlog`.
- **Production Readiness**: Fault-tolerant, scalable, secure, monitorable.