# JSON Connector Deployment Guide

This guide provides instructions to deploy a unified JSON connector for Splunk (CIM-compliant) and/or Elasticsearch (ECS-compliant), parsing large JSON files with multiple schemas. The connector is implemented in Rust for performance and memory efficiency, supporting Docker, Podman, Kubernetes, and Ansible, optimized for high log rates (10,000+ events/second) using asynchronous concurrency.

## Prerequisites

- Rust 1.80+ with Cargo
- Docker or Podman with `docker-compose` or `podman-compose`
- Kubernetes with `kubectl` (for Kubernetes deployment)
- Ansible with `ansible-playbook` and `community.docker` collection (for Ansible deployment)
- (Optional) Splunk instance with HTTP Event Collector (HEC)
- (Optional) Elasticsearch instance (7.x or 8.x)
- JSON files in `/var/log/json_data`
- 2GB memory, 2 CPU cores, 2GB disk space

## File Structure

```
json-connector/
├── deploy_json_connectors.py        # Deployment script (Python-based for compatibility)
├── deploy_config.yaml             # Configuration file
├── src/
│   └── main.rs                   # Rust source for unified connector
├── Cargo.toml                    # Rust dependencies
├── schemas.yaml                  # Schema mappings for JSON parsing
├── Dockerfile                    # Dockerfile for building Rust binary
├── docker-compose.yaml           # Docker/Podman orchestration (single service)
├── json-splunk-deployment.yaml   # Kubernetes manifest for Splunk-enabled connector
├── json-elasticsearch-deployment.yaml # Kubernetes manifest for Elasticsearch-enabled connector
├── json-pvc.yaml                 # Kubernetes PVC for logs
├── deploy_json_connectors.yml    # Ansible playbook
├── README.md                     # This file
├── json_examples.md              # Example JSON inputs and schema details
├── backup/                       # Backup directory
│   └── <timestamp>/              # Timestamped backups
```

## Deployment Steps

1. **Install Dependencies**

   Install Rust and Cargo:
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env
   ```

   Install Ansible dependencies (if using Ansible):
   ```bash
   pip install pyyaml pydantic psutil requests
   ansible-galaxy collection install community.docker
   ```

2. **Prepare Files**

   Place all files in `json-connector/`. Create `/var/log/json_data` with JSON files (see `json_examples.md` for examples).

3. **Configure**

   Edit `deploy_config.yaml` to enable Splunk and/or Elasticsearch and set connection details:
   ```yaml
   json_connectors:
     log_dir: '/var/log/json_data'
     schemas_file: '/app/schemas.yaml'
   splunk:
     enabled: false
     hec_url: 'https://your-splunk-host:8088/services/collector/event'
     hec_token: 'your-splunk-hec-token'
   elasticsearch:
     enabled: false
     host: 'http://localhost:9200'
     index: 'json-logs'
   deployment:
     method: 'docker'  # Options: docker, podman, kubernetes, ansible
     namespace: 'json-connectors'
     kubernetes:
       replicas: 1
       storage_class: 'standard'
       log_storage_size: '10Gi'
   buffer_timeout: 2.0
   worker_count: 4
   batch_size: 100
   ```

   Edit `schemas.yaml` for your JSON schemas (see `json_examples.md` for details).

4. **Build the Rust Binary**

   Build the Rust connector:
   ```bash
   cd json-connector
   cargo build --release
   ```

5. **Deploy**

   - **Docker**:
     ```bash
     python3 deploy_json_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: docker` in `deploy_config.yaml`.

   - **Podman**:
     ```bash
     python3 deploy_json_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: podman` in `deploy_config.yaml`.

   - **Kubernetes**:
     ```bash
     python3 deploy_json_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: kubernetes` and ensure `kubectl` is configured with access to your cluster.

   - **Ansible**:
     ```bash
     ansible-playbook deploy_json_connectors.yml -e "config_file=deploy_config.yaml"
     ```
     Set `deployment.method` to desired platform (docker, podman, or kubernetes).

6. **Verify**

   - Docker/Podman: Check running containers:
     ```bash
     docker ps | grep json-connector
     # or
     podman ps | grep json-connector
     ```
   - Kubernetes: Check pods:
     ```bash
     kubectl get pods -n json-connectors
     ```
   - Splunk: Search for logs:
     ```splunk
     index=json source=json:*
     ```
   - Elasticsearch: Query logs:
     ```bash
     curl http://localhost:9200/json-logs/_search
     ```
   - Logs: View container logs:
     ```bash
     docker logs json-connector
     # or
     kubectl logs -n json-connectors -l app=json-splunk
     ```

## Configuration

- **Environment Variables** (set in `deploy_config.yaml`, `docker-compose.yaml`, or Kubernetes manifests):
  - `JSON_LOG_DIR`: Directory for JSON files (default: `/var/log/json_data`)
  - `SCHEMAS_FILE`: Path to `schemas.yaml` (default: `/app/schemas.yaml`)
  - `CONFIG_FILE`: Path to `deploy_config.yaml` (default: `/app/deploy_config.yaml`)
  - Splunk-specific:
    - `SPLUNK_ENABLED`: Enable Splunk forwarding (true/false, default: false)
    - `SPLUNK_HEC_URL`: Splunk HEC URL
    - `SPLUNK_TOKEN`: Splunk HEC token
  - Elasticsearch-specific:
    - `ES_ENABLED`: Enable Elasticsearch forwarding (true/false, default: false)
    - `ES_HOST`: Elasticsearch host (default: `http://localhost:9200`)
    - `ES_INDEX`: Elasticsearch index (default: `json-logs`)
  - Common:
    - `BATCH_SIZE`: Number of events per batch (default: 100)
    - `BUFFER_TIMEOUT`: Flush timeout in seconds (default: 2.0)
    - `WORKER_COUNT`: Number of worker tasks (default: CPU core count)

## Notes

- **Unified Binary**: The Rust connector (`json-connector`) supports both Splunk and Elasticsearch in a single binary, controlled by `SPLUNK_ENABLED` and `ES_ENABLED`. This reduces deployment complexity compared to separate Python scripts.
- **Performance**: Handles 10,000+ events/second using Tokio’s asynchronous concurrency, with lower memory and CPU usage than Python due to Rust’s zero-cost abstractions.
- **Schema Support**: Add new schemas in `schemas.yaml` for custom formats (see `json_examples.md`).
- **Field Mappings**: Unmapped JSON fields are preserved in `json.raw` (ECS). Configurable CIM/ECS mappings in `schemas.yaml`.
- **Error Handling**: Malformed JSON or missing schemas are logged and skipped, ensuring robust operation.
- **Resource Usage**: Typically requires 1 CPU and 1GB memory, optimized for efficiency.
- **Backups**: Configuration files are backed up to `backup/<timestamp>` during deployment.

## Cleanup

To remove deployed resources:
```bash
python3 deploy_json_connectors.py --config deploy_config.yaml --cleanup
```

For Ansible:
```bash
ansible-playbook deploy_json_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting

- **Missing JSON Files**: Ensure `/var/log/json_data` exists and is writable by the container.
- **Schema Errors**: Verify `schemas.yaml` matches JSON structure as shown in `json_examples.md`.
- **Performance Issues**: Adjust `WORKER_COUNT` (e.g., 8), `BATCH_SIZE` (500-1000), or `BUFFER_TIMEOUT` (1.0s) for optimization.
- **Logs**: Check logs for errors:
  ```bash
  docker logs json-connector
  # or
  kubectl logs -n json-connectors -l app=json-connector
  ```
- **Connectivity**: Verify Splunk HEC (`SPLUNK_HEC_URL`, `SPLUNK_TOKEN`) or Elasticsearch (`ES_HOST`, `ES_INDEX`) settings.

## Customization

- **Schemas**: Add new schemas to `schemas.yaml` for custom JSON formats (see `json_examples.md`).
- **Log Directory**: Update `JSON_LOG_DIR` in configuration files.
- **Parsing Logic**: Modify `src/main.rs` for custom JSON parsing or transformation logic.
- **Dependencies**: Update `Cargo.toml` for additional Rust crates if needed.

## Support

Consult the Rust documentation, Splunk, Elasticsearch, Kubernetes, or Ansible community forums for additional help. Refer to `json_examples.md` for example JSON inputs and schema details.