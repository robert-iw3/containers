# Parquet Connector Deployment Guide (Python)

This guide provides instructions for deploying a Python-based Parquet connector for Elastic (ECS-compliant), processing Parquet files from a specified directory. The connector supports full and incremental processing (using timestamp or row offset), optimized for high data volumes with fault tolerance, Prometheus metrics, and asynchronous processing via `asyncio`.

## Features
- **Data Source**: Parquet files (single or partitioned, supports Snappy/GZIP compression) in a specified directory.
- **Data Capture**: Full file scans or incremental processing via timestamp or row offset.
- **Fault Tolerance**: Persistent state with encrypted SQLite (`sqlcipher`), retries with `tenacity`, structured JSON logging with `structlog`.
- **Monitoring**: Prometheus metrics (events processed, errors, processing latency) at `/metrics` (default port 9000).
- **Scalability**: Concurrent file processing, batching, memory limits, supports high data volumes.
- **Security**: Encrypted state storage, secure credential handling, file path validation.
- **Deployment Options**: Docker, Podman, Kubernetes, Ansible.
- **Dynamic Configuration**: Schema reloading with `watchfiles`.

## Prerequisites
- **Python**: 3.12+ with `pip`.
- **Container Runtime**: Docker or Podman with `docker-compose` or `podman-compose`.
- **Kubernetes**: `kubectl` for Kubernetes deployments.
- **Ansible**: `ansible-playbook` with `community.docker` collection.
- **Elastic**: Elasticsearch instance with Bulk API access.
- **System Resources**: 2GB memory, 2 CPU cores, 2GB disk space.
- **Dependencies**:
  ```bash
  pip install -r requirements.txt
  ansible-galaxy collection install community.docker
  ```

## File Structure
```
parquet-connector/
├── src/
│   ├── main.py                    # Main entry point
│   ├── handler.py                # Parquet file processing logic
│   ├── schema.py                 # Schema parsing logic
│   ├── sender.py                 # Elastic sender logic
├── requirements.txt               # Python dependencies
├── deploy_parquet_connectors.py  # Deployment script
├── deploy_config.yaml            # Configuration file
├── schemas.yaml                  # Schema mappings
├── Dockerfile                    # Container build
├── docker-compose.yml            # Docker/Podman orchestration
├── parquet-elastic-deployment.yaml # Kubernetes manifest
├── deploy_parquet_connectors.yml # Ansible playbook
├── README.md                     # This file
├── backup/                      # Backup directory
├── data/                        # Parquet files directory
```

## Deployment Steps

### 1. Prepare Files
Place all files in `parquet-connector/`. Ensure Parquet files are in the `data/` directory with read permissions.

### 2. Configure
Edit `deploy_config.yaml`:
```yaml
parquet_connectors:
  schemas_file: '/app/schemas.yaml'
  state_path: '/app/state.db'
elastic:
  host: 'http://localhost:9200'
  index: 'parquet-logs'
parquet:
  data_dir: '/app/data'
  max_memory_mb: 1024
deployment:
  method: 'docker'
  namespace: 'parquet-connectors'
  kubernetes:
    replicas: 1
buffer_timeout: 2.0
worker_count: 4
batch_size: 100
poll_interval: 60
incremental_enabled: false
max_files_concurrent: 5
metrics_port: 9000
sqlcipher_key: 'your-secure-key'
python_logging_level: 'INFO'
```

NOTE: It is important to map the fields from parquet to Elastic Common Schema (provided is an example)

Refer to `schema_guide_python.md` for further detailed instructions.

Edit `schemas.yaml`:
```yaml
schemas:
  - name: network_events
    file_name: network_events.parquet
    timestamp_field: timestamp
    mappings:
      ecs:
        '@timestamp': timestamp
        'event.category': category
        'source.ip': source_ip
        'source.port': source_port
        'destination.ip': dest_ip
        'destination.port': dest_port
        'network.protocol': protocol
        'network.bytes': bytes_received
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
  python3 deploy_parquet_connectors.py --config deploy_config.yaml
  ```
- **Ansible**:
  ```bash
  ansible-playbook deploy_parquet_connectors.yml -e "config_file=deploy_config.yaml"
  ```

### 5. Verify
- Containers: `docker ps` or `podman ps`
- Pods: `kubectl get pods -n parquet-connectors`
- Elastic: Query index `parquet-logs` in Kibana/ES.
- Metrics: `curl http://localhost:9000/metrics`
- Logs: `docker logs parquet-elastic` or `kubectl logs -n parquet-connectors -l app=parquet-elastic`

## Configuration
- **Environment Variables**:
  - `SCHEMAS_FILE`, `STATE_PATH`, `ES_HOST`, `ES_INDEX`, `DATA_DIR`, `BATCH_SIZE`, `BUFFER_TIMEOUT`, `WORKER_COUNT`, `POLL_INTERVAL`, `INCREMENTAL_ENABLED`, `MAX_FILES_CONCURRENT`, `MAX_MEMORY_MB`, `METRICS_PORT`, `SQLCIPHER_KEY`, `PYTHON_LOGGING_LEVEL`.

## Production Considerations
- **Performance**: Optimized with batching, concurrent file processing, async I/O, and memory limits. Tune `BATCH_SIZE`, `POLL_INTERVAL`, `MAX_FILES_CONCURRENT`, `MAX_MEMORY_MB`.
- **Fault Tolerance**: Persistent state, retries, logging, graceful shutdown.
- **Security**: Encrypted state with `sqlcipher`, secure credential handling, file path validation.
- **Monitoring**: Prometheus metrics at `/metrics`. Integrate with Grafana.
- **Dynamic Schemas**: Automatic reload on `schemas.yaml` changes.
- **Parquet Support**: Handles single files, partitioned datasets, and compressed files (Snappy/GZIP).

## Cleanup
```bash
python3 deploy_parquet_connectors.py --config deploy_config.yaml --cleanup
```
Ansible:
```bash
ansible-playbook deploy_parquet_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting
- **File Access Issues**: Verify `DATA_DIR` permissions and Parquet file integrity.
- **Schema Mismatches**: Ensure Parquet schemas match `schemas.yaml`. Check logs for missing fields.
- **Performance**: Adjust `BATCH_SIZE`, `POLL_INTERVAL`, `MAX_FILES_CONCURRENT`, `MAX_MEMORY_MB`.
- **Logs**: Set `PYTHON_LOGGING_LEVEL=DEBUG`.

## Validation and Error Checking
- **Syntax**: Python files pass `flake8`, `mypy`, and `black`. YAML files validated post-rendering.
- **Dependencies**: Updated to latest versions, compatible with Python 3.12.
- **Interoperability**: Supports Parquet files (including partitioned/compressed), all deployment methods.
- **Error Handling**: Custom exceptions, retries with `tenacity`, detailed logging with `structlog`.
- **Production Readiness**: Secure, scalable, fault-tolerant, monitorable.