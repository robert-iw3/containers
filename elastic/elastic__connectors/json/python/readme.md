# JSON Connector Deployment Guide

This guide provides instructions to deploy separate JSON connectors for Splunk (CIM-compliant) and Elasticsearch (ECS-compliant), parsing large JSON files with multiple schemas. The connectors support Docker, Podman, Kubernetes, and Ansible, optimized for high log rates (10,000+ events/second) using multiprocessing.

## Prerequisites

- Python 3.8+ with `pydantic`, `pyyaml`, `psutil`, `requests`, `elasticsearch_async`, `aiohttp`, `orjson`, `watchdog`
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
├── deploy_json_connectors.py        # Unified deployment script
├── deploy_config.yaml             # Configuration file
├── json_splunk_connector.py       # Splunk connector
├── json_elasticsearch_connector.py # Elasticsearch connector
├── schemas.yaml                  # Schema mappings
├── Dockerfile.connector           # Dockerfile for connectors
├── docker-compose.yml            # Docker/Podman orchestration
├── json-splunk-deployment.yaml   # Kubernetes manifest for Splunk
├── json-elasticsearch-deployment.yaml # Kubernetes manifest for Elasticsearch
├── json-pvc.yaml                 # Kubernetes PVC for logs
├── deploy_json_connectors.yml    # Ansible playbook
├── README.md                    # This file
├── backup/                      # Backup directory
│   └── <timestamp>/             # Timestamped backups
```

## Deployment Steps

1. **Install Dependencies**
   ```bash
   pip install pyyaml pydantic psutil requests elasticsearch_async aiohttp orjson watchdog
   ansible-galaxy collection install community.docker
   ```

2. **Prepare Files**
   Place all files in `json-connector/`. Create `/var/log/json_data` with JSON files.

3. **Configure**
   Edit `deploy_config.yaml`:
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
   Edit `schemas.yaml` for your JSON schemas:
   ```yaml
   schemas:
     - name: simple_event
       schema_key: event_type
       schema_value: network_event
       mappings:
         ecs:
           timestamp: timestamp
           event_id: id
           source_ip: source.ip
         cim:
           time: timestamp
           event_id: id
           source: source.ip
     - name: scada_modbus
       schema_key: event_type
       schema_value: modbus_event
       mappings:
         ecs:
           timestamp: timestamp
           event_id: transaction_id
           source_ip: client.ip
         cim:
           time: timestamp
           event_id: transaction_id
           source: client.ip
   ```

4. **Deploy**
   - **Docker**:
     ```bash
     python3 deploy_json_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: docker`.
   - **Podman**:
     ```bash
     python3 deploy_json_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: podman`.
   - **Kubernetes**:
     ```bash
     python3 deploy_json_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: kubernetes` and ensure `kubectl` is configured.
   - **Ansible**:
     ```bash
     ansible-playbook deploy_json_connectors.yml -e "config_file=deploy_config.yaml"
     ```
     Set `deployment.method` to desired platform.

5. **Verify**
   - Docker/Podman: `docker ps` or `podman ps`
   - Kubernetes: `kubectl get pods -n json-connectors`
   - Splunk: `index=json source=json:*`
   - Elasticsearch: `curl http://localhost:9200/json-logs/_search`
   - Logs: `docker logs json-splunk` or `kubectl logs -n json-connectors -l app=json-splunk`

## Configuration
- **Environment Variables** (set in `deploy_config.yaml`, `docker-compose.yml`, or Kubernetes manifests):
  - `JSON_LOG_DIR`: JSON file directory (default: `/var/log/json_data`)
  - `SCHEMAS_FILE`: Path to `schemas.yaml` (default: `/app/schemas.yaml`)
  - Splunk:
    - `SPLUNK_HEC_URL`: HEC URL
    - `SPLUNK_TOKEN`: HEC token
  - Elasticsearch:
    - `ES_HOST`: Host (default: `http://localhost:9200`)
    - `ES_INDEX`: Index (default: `json-logs`)
  - Common:
    - `BATCH_SIZE`: Batch size (default: 100)
    - `BUFFER_TIMEOUT`: Flush timeout (default: 2.0s)
    - `WORKER_COUNT`: Workers (default: CPU core count)

## Example JSON Inputs
**simple_event.json**:
```json
{"event_type":"network_event","id":"12345","timestamp":"2025-08-27T22:42:00Z","category":"network","source":{"ip":"192.168.1.10","port":12345},"destination":{"ip":"10.0.0.20","port":80},"protocol":"tcp","bytes_sent":1024,"bytes_received":2048,"action":"allowed"}
```

**scada_modbus.json**:
```json
{"event_type":"modbus_event","transaction_id":"67890","timestamp":"2025-08-27T22:42:01Z","client":{"ip":"192.168.1.100","port":502},"server":{"ip":"10.0.0.200","port":502},"function_code":3}
```

## Notes
- **Performance**: Each connector handles 10,000+ events/second with multiprocessing.
- **Schema Support**: Add schemas in `schemas.yaml` for custom formats.
- **Field Mappings**: All JSON fields in `json.raw` (ECS). Configurable CIM/ECS mappings.
- **Error Handling**: Malformed JSON logged and skipped.
- **Resource Usage**: 1 CPU, 1GB memory per connector.
- **Backups**: Stored in `backup/<timestamp>`.

## Cleanup
```bash
python3 deploy_json_connectors.py --config deploy_config.yaml --cleanup
```
For Ansible:
```bash
ansible-playbook deploy_json_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting
- **Missing JSON Files**: Verify `/var/log/json_data` is writable.
- **Schema Errors**: Check `schemas.yaml` for correct `schema_key`/`schema_value`.
- **Performance**: Adjust `WORKER_COUNT` (e.g., 8), `BATCH_SIZE` (500-1000), or `BUFFER_TIMEOUT` (1s).
- **Logs**: `docker logs json-splunk` or `kubectl logs -n json-connectors -l app=json-splunk`

## Customization
- **Schemas**: Extend `schemas.yaml` for new JSON formats.
- **Log Directory**: Change `JSON_LOG_DIR`.
- **Parsing Logic**: Modify `json_splunk_connector.py` or `json_elasticsearch_connector.py`.

## Support
Consult Python, Splunk, Elasticsearch, Kubernetes, or Ansible documentation or community forums.