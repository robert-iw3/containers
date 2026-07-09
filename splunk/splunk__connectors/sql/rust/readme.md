# SQL Connector Deployment Guide

This guide provides instructions for deploying a Rust-based SQL connector for Splunk (CIM-compliant), querying tables/views from Microsoft SQL Server, MySQL, PostgreSQL, SQLite, or Oracle databases. The connector supports polling and PostgreSQL Change Data Capture (CDC) for real-time streaming, optimized for high data volumes with fault tolerance, Prometheus metrics, and asynchronous processing via Tokio.

## Features
- **Database Support**: Microsoft SQL Server, MySQL, PostgreSQL, SQLite, Oracle.
- **Data Capture**: Incremental polling (timestamp/UUID) or PostgreSQL CDC via logical replication.
- **Fault Tolerance**: Persistent state with `sled`, connection retries, structured JSON logging.
- **Monitoring**: Prometheus metrics (events processed, errors, query latency) at `/metrics` (default port 9000).
- **Scalability**: Per-table connection pooling, batching, supports 10,000+ events/second.
- **Security**: Credentials via environment variables, TLS support via `sqlx`.
- **Deployment Options**: Docker, Podman, Kubernetes, Ansible.

## Prerequisites
- **Rust**: 1.73+ with `cargo`.
- **Container Runtime**: Docker or Podman with `docker-compose` or `podman-compose`.
- **Kubernetes**: `kubectl` for Kubernetes deployments.
- **Ansible**: `ansible-playbook` with `community.docker` collection.
- **Splunk**: HTTP Event Collector (HEC) configured.
- **Database**: Read access to tables/views; for PostgreSQL CDC, logical replication enabled.
- **System Resources**: 2GB memory, 2 CPU cores, 2GB disk space.
- **Dependencies**:
  ```bash
  apk add --no-cache rust cargo musl-dev libgcc
  ansible-galaxy collection install community.docker
  ```

## File Structure
```
sql-connector/
├── src/
│   ├── main.rs                    # Main entry point
│   ├── handler.rs                # Database polling and CDC logic
│   ├── schema.rs                 # Schema parsing logic
│   ├── sender.rs                 # Splunk sender logic
├── Cargo.toml                    # Rust dependencies
├── deploy_sql_connectors.rs      # Deployment script
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
Place all files in `sql-connector/`. Ensure database access and, for PostgreSQL CDC, logical replication (`wal_level = logical` in `postgresql.conf`).

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

Edit `schemas.yaml` for your tables/views:
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

### 3. Build
```bash
cargo build --release
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
  cargo run --release --bin deploy_sql_connectors -- --config deploy_config.yaml
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
- Logs: `docker logs sql-splunk` or `kubectl logs -n sql://localhost:9000/metrics`
- Logs: `docker logs sql-splunk` or `kubectl logs -n sql-connectors -l app=sql-splunk`

## Configuration
- **Environment Variables**:
  - `SCHEMAS_FILE`, `STATE_PATH`, `SPLUNK_HEC_URL`, `SPLUNK_TOKEN`, `DB_TYPE`, `DB_CONN_STR`, `BATCH_SIZE`, `BUFFER_TIMEOUT`, `WORKER_COUNT`, `POLL_INTERVAL`, `CDC_ENABLED`, `MAX_CONNECTIONS_PER_TABLE`, `METRICS_PORT`, `RUST_LOG`.

## Production Considerations
- **Performance**: Handles large datasets with batching and per-table pools. Tune `BATCH_SIZE`, `POLL_INTERVAL`, `MAX_CONNECTIONS_PER_TABLE`.
- **Fault Tolerance**: Persistent state, retries, logging, graceful shutdown.
- **Security**: Use secrets for `DB_CONN_STR`, `SPLUNK_TOKEN`. Enable TLS in `DB_CONN_STR`.
- **Monitoring**: Prometheus metrics at `/metrics`. Integrate with Grafana for dashboards.
- **CDC**: Requires PostgreSQL logical replication setup (publication and slot).

## Cleanup
```bash
cargo run --release --bin deploy_sql_connectors -- --config deploy_config.yaml --cleanup
```
Ansible:
```bash
ansible-playbook deploy_sql_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting
- **Connection Issues**: Verify `DB_CONN_STR`, network, and database permissions.
- **CDC Errors**: Ensure PostgreSQL `wal_level=logical`, replication role.
- **Performance**: Adjust `BATCH_SIZE`, `POLL_INTERVAL`, `MAX_CONNECTIONS_PER_TABLE`.
- **Logs**: Set `RUST_LOG=debug`.