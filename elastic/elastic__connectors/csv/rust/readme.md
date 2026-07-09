# CSV Connector Deployment Guide

This guide provides instructions to deploy a Rust-based CSV connector for Splunk (CIM-compliant) and Elasticsearch (ECS-compliant), parsing large CSV files from multiple sources with varying schemas. The connector supports Docker, Podman, Kubernetes, and Ansible, optimized for high log rates (10,000+ events/second) using asynchronous processing and Tokio.

## Prerequisites

- Rust 1.73+ with `cargo`
- Docker or Podman with `docker-compose` or `podman-compose`
- Kubernetes with `kubectl` (for Kubernetes deployment)
- Ansible with `ansible-playbook` and `community.docker` collection (for Ansible deployment)
- (Optional) Splunk instance with HTTP Event Collector (HEC)
- (Optional) Elasticsearch instance (7.x or 8.x)
- CSV files in `/var/log/csv_data`
- 2GB memory, 2 CPU cores, 2GB disk space

## File Structure
```
csv-connector/
├── src/
│   ├── main.rs                    # Main entry point
│   ├── handler.rs                # File event handling logic
│   ├── schema.rs                 # Schema parsing logic
│   ├── sender.rs                 # Splunk/Elasticsearch sender logic
├── Cargo.toml                    # Rust dependencies and build settings
├── deploy_csv_connectors.rs      # Unified deployment script
├── deploy_config.yaml            # Configuration file
├── schemas.yaml                  # Schema mappings
├── Dockerfile                    # Dockerfile for connector
├── docker-compose.yml            # Docker/Podman orchestration
├── csv-splunk-deployment.yaml    # Kubernetes manifest for Splunk
├── csv-elasticsearch-deployment.yaml # Kubernetes manifest for Elasticsearch
├── csv-pvc.yaml                 # Kubernetes PVC for logs
├── deploy_csv_connectors.yml     # Ansible playbook
├── README.md                    # This file
├── csv_examples.md              # Example CSV inputs
├── backup/                      # Backup directory
│   └── <timestamp>/             # Timestamped backups
```

## Deployment Steps

1. **Install Dependencies**
   ```bash
   apk add --no-cache rust cargo musl-dev libgcc
   ansible-galaxy collection install community.docker
   ```

2. **Prepare Files**
   Place all files in `csv-connector/`. Create `/var/log/csv_data` with CSV files.

3. **Configure**
   Edit `deploy_config.yaml`:
   ```yaml
   csv_connectors:
     log_dir: '/var/log/csv_data'
     schemas_file: '/app/schemas.yaml'
   splunk:
     enabled: false
     hec_url: 'https://your-splunk-host:8088/services/collector/event'
     hec_token: 'your-splunk-hec-token'
   elasticsearch:
     enabled: false
     host: 'http://localhost:9200'
     index: 'csv-logs'
   deployment:
     method: 'docker'  # Options: docker, podman, kubernetes, ansible
     namespace: 'csv-connectors'
     kubernetes:
       replicas: 1
       storage_class: 'standard'
       log_storage_size: '10Gi'
   buffer_timeout: 2.0
   worker_count: 4
   batch_size: 100
   delimiter: ','
   ```
   Edit `schemas.yaml` for your CSV schemas:
   ```yaml
   schemas:
     - name: simple_event
       schema_key: event_type
       schema_value: network_event
       mappings:
         ecs:
           timestamp: timestamp
           event_id: id
           source_ip: source_ip
         cim:
           time: timestamp
           event_id: id
           source: source_ip
     - name: scada_modbus
       schema_key: event_type
       schema_value: modbus_event
       mappings:
         ecs:
           timestamp: timestamp
           event_id: transaction_id
           source_ip: client_ip
         cim:
           time: timestamp
           event_id: transaction_id
           source: client_ip
   ```

4. **Deploy**
   - **Docker**:
     ```bash
     cargo build --release
     docker-compose up -d --build
     ```
     Set `deployment.method: docker`.
   - **Podman**:
     ```bash
     cargo build --release
     podman-compose up -d --build
     ```
     Set `deployment.method: podman`.
   - **Kubernetes**:
     ```bash
     cargo build --release
     cargo run --release --bin deploy_csv_connectors -- --config deploy_config.yaml
     ```
     Set `deployment.method: kubernetes` and ensure `kubectl` is configured.
   - **Ansible**:
     ```bash
     cargo build --release
     ansible-playbook deploy_csv_connectors.yml -e "config_file=deploy_config.yaml"
     ```
     Set `deployment.method` to desired platform.

5. **Verify**
   - Docker/Podman: `docker ps` or `podman ps`
   - Kubernetes: `kubectl get pods -n csv-connectors`
   - Splunk: `index=csv source=csv:*`
   - Elasticsearch: `curl http://localhost:9200/csv-logs/_search`
   - Logs: `docker logs csv-splunk` or `kubectl logs -n csv-connectors -l app=csv-splunk`

## Configuration
- **Environment Variables** (set in `deploy_config.yaml`, `docker-compose.yml`, or Kubernetes manifests):
  - `CSV_LOG_DIR`: CSV file directory (default: `/var/log/csv_data`)
  - `SCHEMAS_FILE`: Path to `schemas.yaml` (default: `/app/schemas.yaml`)
  - Splunk:
    - `SPLUNK_HEC_URL`: HEC URL
    - `SPLUNK_TOKEN`: HEC token
  - Elasticsearch:
    - `ES_HOST`: Host (default: `http://localhost:9200`)
    - `ES_INDEX`: Index (default: `csv-logs`)
  - Common:
    - `BATCH_SIZE`: Batch size (default: 100)
    - `BUFFER_TIMEOUT`: Flush timeout (default: 2.0s)
    - `WORKER_COUNT`: Workers (default: CPU core count)
    - `CSV_DELIMITER`: Default delimiter (default: `,`)
    - `ENABLE_SPLUNK`: Enable Splunk mode (default: `false`)

## Example CSV Inputs
See `csv_examples.md` for detailed examples of supported CSV formats, including:
- `simple_event.csv`: Network traffic logs
- `scada_modbus.csv`: Modbus protocol events
- `network_flow.csv`: NetFlow or firewall logs
- `authentication.csv`: Authentication events
- `ids_alert.csv`: IDS/IPS alerts
- `scada_dnp3.csv`: DNP3 protocol events

## Notes
- **Performance**: The Rust connector handles 10,000+ events/second with Tokio-based asynchronous processing.
- **Schema Support**: Add schemas in `schemas.yaml` for custom formats.
- **Field Mappings**: All CSV fields in `csv.raw` (ECS). Configurable CIM/ECS mappings.
- **Error Handling**: Malformed CSV rows logged and skipped.
- **Resource Usage**: 1 CPU, 1GB memory per connector.
- **Backups**: Stored in `backup/<timestamp>`.

## Cleanup
```bash
cargo run --release --bin deploy_csv_connectors -- --config deploy_config.yaml --cleanup
```
For Ansible:
```bash
ansible-playbook deploy_csv_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting
- **Missing CSV Files**: Verify `/var/log/csv_data` is writable.
- **Schema Errors**: Check `schemas.yaml` for correct `schema_key`/`schema_value`.
- **Delimiter Issues**: Set `CSV_DELIMITER` or rely on auto-detection.
- **Performance**: Adjust `WORKER_COUNT` (e.g., 8), `BATCH_SIZE` (500-1000), or `BUFFER_TIMEOUT` (1s).
- **Logs**: `docker logs csv-splunk` or `kubectl logs -n csv-connectors -l app=csv-splunk`

## Customization
- **Schemas**: Extend `schemas.yaml` for new CSV formats.
- **Log Directory**: Change `CSV_LOG_DIR`.
- **Parsing Logic**: Modify `src/handler.rs` for custom parsing.

## Support
Consult Rust, Splunk, Elasticsearch, Kubernetes, or Ansible documentation or community forums.