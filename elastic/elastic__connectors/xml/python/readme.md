# XML Connector Deployment Guide

This guide provides instructions to deploy separate XML connectors for Splunk (CIM-compliant) and Elasticsearch (ECS-compliant), parsing large XML files with multiple schemas. The connectors support Docker, Podman, Kubernetes, and Ansible, optimized for high log rates (10,000+ events/second) using multiprocessing.

## Prerequisites

- Python 3.8+ with `pydantic`, `pyyaml`, `psutil`, `requests`, `elasticsearch_async`, `aiohttp`, `orjson`, `watchdog`, `lxml`
- Docker or Podman with `docker-compose` or `podman-compose`
- Kubernetes with `kubectl` (for Kubernetes deployment)
- Ansible with `ansible-playbook` and `community.docker` collection (for Ansible deployment)
- (Optional) Splunk instance with HTTP Event Collector (HEC)
- (Optional) Elasticsearch instance (7.x or 8.x)
- XML files in `/var/log/xml_data`
- 2GB memory, 2 CPU cores, 2GB disk space

## File Structure
```
xml-connector/
├── deploy_xml_connectors.py        # Unified deployment script
├── deploy_config.yaml             # Configuration file
├── xml_splunk_connector.py        # Splunk connector
├── xml_elasticsearch_connector.py # Elasticsearch connector
├── schemas.yaml                  # Schema mappings
├── Dockerfile.connector           # Dockerfile for connectors
├── docker-compose.yml            # Docker/Podman orchestration
├── xml-splunk-deployment.yaml    # Kubernetes manifest for Splunk
├── xml-elasticsearch-deployment.yaml # Kubernetes manifest for Elasticsearch
├── xml-pvc.yaml                  # Kubernetes PVC for logs
├── deploy_xml_connectors.yml     # Ansible playbook
├── README.md                    # This file
├── backup/                      # Backup directory
│   └── <timestamp>/             # Timestamped backups
```

## Deployment Steps

1. **Install Dependencies**
   ```bash
   pip install pyyaml pydantic psutil requests elasticsearch_async aiohttp orjson watchdog lxml
   ansible-galaxy collection install community.docker
   ```

2. **Prepare Files**
   Place all files in `xml-connector/`. Create `/var/log/xml_data` with XML files.

3. **Configure**
   Edit `deploy_config.yaml`:
   ```yaml
   xml_connectors:
     log_dir: '/var/log/xml_data'
     schemas_file: '/app/schemas.yaml'
   splunk:
     enabled: false
     hec_url: 'https://your-splunk-host:8088/services/collector/event'
     hec_token: 'your-splunk-hec-token'
   elasticsearch:
     enabled: false
     host: 'http://localhost:9200'
     index: 'xml-logs'
   deployment:
     method: 'docker'  # Options: docker, podman, kubernetes, ansible
     namespace: 'xml-connectors'
     kubernetes:
       replicas: 1
       storage_class: 'standard'
       log_storage_size: '10Gi'
   buffer_timeout: 2.0
   worker_count: 4
   batch_size: 100
   ```
   Edit `schemas.yaml` for your XML schemas:
   ```yaml
   schemas:
     - name: simple_event
       root_element: event
       namespace: "http://example.com/simple"
       mappings:
         ecs:
           timestamp: timestamp
           event_id: id
           source_ip: source/ip
         cim:
           time: timestamp
           event_id: id
           source: source/ip
     - name: scada_modbus
       root_element: modbus_event
       namespace: "http://example.com/scada"
       mappings:
         ecs:
           timestamp: timestamp
           event_id: transaction_id
           source_ip: client/ip
         cim:
           time: timestamp
           event_id: transaction_id
           source: client/ip
   ```

4. **Deploy**
   - **Docker**:
     ```bash
     python3 deploy_xml_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: docker`.
   - **Podman**:
     ```bash
     python3 deploy_xml_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: podman`.
   - **Kubernetes**:
     ```bash
     python3 deploy_xml_connectors.py --config deploy_config.yaml
     ```
     Set `deployment.method: kubernetes` and ensure `kubectl` is configured.
   - **Ansible**:
     ```bash
     ansible-playbook deploy_xml_connectors.yml -e "config_file=deploy_config.yaml"
     ```
     Set `deployment.method` to desired platform.

5. **Verify**
   - Docker/Podman: `docker ps` or `podman ps`
   - Kubernetes: `kubectl get pods -n xml-connectors`
   - Splunk: `index=xml source=xml:*`
   - Elasticsearch: `curl http://localhost:9200/xml-logs/_search`
   - Logs: `docker logs xml-splunk` or `kubectl logs -n xml-connectors -l app=xml-splunk`

## Configuration
- **Environment Variables** (set in `deploy_config.yaml`, `docker-compose.yml`, or Kubernetes manifests):
  - `XML_LOG_DIR`: XML file directory (default: `/var/log/xml_data`)
  - `SCHEMAS_FILE`: Path to `schemas.yaml` (default: `/app/schemas.yaml`)
  - Splunk:
    - `SPLUNK_HEC_URL`: HEC URL
    - `SPLUNK_TOKEN`: HEC token
  - Elasticsearch:
    - `ES_HOST`: Host (default: `http://localhost:9200`)
    - `ES_INDEX`: Index (default: `xml-logs`)
  - Common:
    - `BATCH_SIZE`: Batch size (default: 100)
    - `BUFFER_TIMEOUT`: Flush timeout (default: 2.0s)
    - `WORKER_COUNT`: Workers (default: CPU core count)

## Notes
- **Performance**: Each connector handles 10,000+ events/second with multiprocessing.
- **Schema Support**: Add schemas in `schemas.yaml` for formats like STIX, NIEM.
- **Field Mappings**: All XML fields in `xml.raw` (ECS). Configurable CIM/ECS mappings.
- **Error Handling**: Malformed XML logged and skipped.
- **Resource Usage**: 1 CPU, 1GB memory per connector.
- **Backups**: Stored in `backup/<timestamp>`.

## Cleanup
```bash
python3 deploy_xml_connectors.py --config deploy_config.yaml --cleanup
```
For Ansible:
```bash
ansible-playbook deploy_xml_connectors.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Troubleshooting
- **Missing XML Files**: Verify `/var/log/xml_data` is writable.
- **Schema Errors**: Check `schemas.yaml` for correct root elements/namespaces.
- **Performance**: Adjust `WORKER_COUNT` (e.g., 8), `BATCH_SIZE` (500-1000), or `BUFFER_TIMEOUT` (1s).
- **Logs**: `docker logs xml-splunk` or `kubectl logs -n xml-connectors -l app=xml-splunk`

## Customization
- **Schemas**: Extend `schemas.yaml` for new XML formats.
- **Log Directory**: Change `XML_LOG_DIR`.
- **Parsing Logic**: Modify `xml_splunk_connector.py` or `xml_elasticsearch_connector.py`.

## Support
Consult Python, Splunk, Elasticsearch, Kubernetes, or Ansible documentation or community forums.