# Zeek Deployment Guide

This guide provides instructions to deploy Zeek using a Python deployment script, supporting Docker, Podman, Kubernetes, or Ansible. The setup includes enhanced security, performance optimizations, monitoring capabilities, and optional integration with Splunk and Elasticsearch.

## Prerequisites

- Python 3.8+ with `pydantic`, `pyyaml`, `psutil`, `requests`, `elasticsearch_async`, `aiohttp`, `orjson`, `watchdog`, `prometheus_client`
- One of the following:
  - Docker and Docker Compose
  - Podman and podman-compose
  - Kubernetes (kubectl)
  - Ansible (with `community.docker` collection)
- Root or sudo privileges
- Network interface for packet capture
- Approximately 2GB of disk space
- Internet access for pulling Docker images and Zeek packages
- (Optional) Splunk instance with HTTP Event Collector (HEC) enabled
- (Optional) Elasticsearch instance (version 7.x or 8.x)

## File Structure
```console
.
├── zeek_connector.py
├── Dockerfile.connector
├── docker-compose.yml
├── deploy_zeek.py
├── deploy_config.yaml
├── Dockerfile
├── entrypoint.sh
├── prometheus.yml
├── zeek_exporter.py
├── etc/
│   ├── networks.cfg
│   ├── zeekctl.cfg
│   ├── node.cfg
├── share/zeek/site/
│   ├── local.zeek
│   ├── login.zeek
│   ├── known-routers.zeek
│   ├── guess.zeek
│   ├── guess_ics_map.txt
├── backup/<timestamp>/
├── /var/log/zeek/
├── /var/spool/zeek/
```

## Deployment Steps

1. **Install Python Dependencies**
   ```bash
   pip install pyyaml pydantic psutil requests elasticsearch_async aiohttp orjson watchdog prometheus_client
   ```

2. **Clone the Repository or Copy Files**
   Ensure all required files (`deploy_zeek.py`, `deploy_config.yaml`, `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `prometheus.yml`, `zeek_exporter.py`, `zeek_connector.py`, `Dockerfile.connector`, `etc/`, `share/zeek/site/`) are in your working directory.

3. **Create Configuration File**
   Create a `deploy_config.yaml` file to customize settings. Example:
   ```yaml
   zeek:
     version: '8.0.4'
     interface: 'eth0'
     log_dir: '/var/log/zeek'
     spool_dir: '/var/spool/zeek'
     worker_processes: 4
     network_mode: 'host'
     cluster:
       enabled: false
       nodes:
         - type: manager
           host: localhost
         - type: proxy
           host: localhost
         - type: worker
           host: localhost
           interface: eth0
   security:
     restrict_filters: 'tcp port 80 or tcp port 443'
     disable_ssl_validation: false
     enable_json_logs: true
     disable_password_logging: true
   splunk:
     enabled: false
     hec_url: 'https://your-splunk-host:8088/services/collector/event'
     hec_token: 'your-splunk-hec-token'
   elasticsearch:
     enabled: false
     host: 'http://localhost:9200'
     index: 'zeek-logs'
   deployment:
     method: 'docker'  # Options: docker, podman, kubernetes, ansible
     namespace: 'zeek'
     container_name: 'zeek-monitor'
   buffer_timeout: 5.0
   worker_count: 4  # Number of worker processes (default: CPU core count)
   ```
   - `worker_processes` is capped at available CPU cores.
   - Set `cluster.enabled` to `true` for multi-node deployments.
   - Enable `splunk.enabled` or `elasticsearch.enabled` for log forwarding.
   - Adjust `worker_count` based on CPU cores and log volume (e.g., 4-8 for high log rates).

4. **Create ICS Protocol Mapping (Optional)**
   The `guess_ics_map.txt` file defines ICS protocol mappings for `guess.zeek`. Customize it in `share/zeek/site/guess_ics_map.txt` if needed. Default:
   ```
   # proto dport sport name category
   tcp 502 0 modbus ICS
   tcp 44818 0 enip ICS
   udp 47808 0 bacnet ICS
   ```

5. **Run the Deployment Script**
   ```bash
   python3 deploy_zeek.py --config deploy_config.yaml
   ```
   - The script validates configurations, sets secure permissions, and backs up files to `backup/<timestamp>`.
   - Use `--cleanup` to remove the deployment.

6. **Verify Deployment**
   - Docker/Podman:
     ```bash
     docker ps  # or podman ps
     ```
   - Kubernetes:
     ```bash
     kubectl get pods -n zeek
     ```
   - Ansible:
     ```bash
     cat zeek_deployment.log
     ```
   - Check health:
     ```bash
     docker-compose ps  # or kubectl describe pod -n zeek
     ```

7. **Access Zeek Logs**
   Logs are in `/var/log/zeek` (or configured `log_dir`). Key logs include:
   - `conn.log`: Connection details
   - `http.log`: HTTP traffic
   - `bestguess.log`: ICS protocol guesses
   - `known_routers.log`: Detected routers
   - `stats.log`: Performance metrics

8. **Monitor with Prometheus**
   Access Prometheus at `http://localhost:9090` to view Zeek metrics (e.g., packet loss, connection rates) from `stats.log` via the `zeek-exporter` service (port 9911).

## Optional Splunk and Elasticsearch Integration
The `zeek_connector.py` script enables forwarding Zeek logs to Splunk (CIM-compliant) and Elasticsearch (ECS-compliant) in real-time. It supports `conn.log` and `http.log`, mapping all default Zeek fields to appropriate schemas, with multiprocessing for high log rates.

### Setup
1. **Install Additional Dependencies**
   ```bash
   pip install requests elasticsearch_async aiohttp orjson watchdog
   ```

2. **Configure Splunk**
   - Enable HTTP Event Collector (HEC) in Splunk.
   - Obtain the HEC token and endpoint URL (e.g., `https://your-splunk-host:8088/services/collector/event`).
   - Update `deploy_config.yaml` with:
     ```yaml
     splunk:
       enabled: true
       hec_url: 'https://your-splunk-host:8088/services/collector/event'
       hec_token: 'your-splunk-hec-token'
     ```

3. **Configure Elasticsearch**
   - Ensure Elasticsearch is running (e.g., `http://localhost:9200`).
   - Update `deploy_config.yaml` with:
     ```yaml
     elasticsearch:
       enabled: true
       host: 'http://localhost:9200'
       index: 'zeek-logs'
     ```

4. **Configure Multiprocessing**
   - Set `worker_count` in `deploy_config.yaml` or via environment variable `WORKER_COUNT` (e.g., 4 for quad-core systems, 8 for high log rates).
   - Adjust `batch_size` (default: 100) and `buffer_timeout` (default: 5 seconds) for optimal throughput and latency.

5. **Deploy the Connector**
   - The connector runs as a separate service in `docker-compose.yml`.
   - Ensure `zeek_connector.py` and `Dockerfile.connector` are in the root directory.
   - Deploy with:
     ```bash
     python3 deploy_zeek.py --config deploy_config.yaml
     ```
   - The connector monitors `/var/log/zeek` and forwards logs to enabled destinations using multiple worker processes.

6. **Verify Integration**
   - Splunk: Search for Zeek logs using `index=zeek source=zeek:*`. Supported fields include `source`, `dest`, `protocol`, `http_method`, `url`, `http_user_agent`, `bytes_in`, `bytes_out`, etc.
   - Elasticsearch: Query the `zeek-logs` index using Kibana or `curl http://localhost:9200/zeek-logs/_search`. Supported fields include `source.ip`, `destination.ip`, `network.protocol`, `http.request.method`, `url.path`, `http.request.user_agent`, etc.
   - Check connector logs:
     ```bash
     docker logs zeek-connector
     ```

### Notes
- **Field Mappings**:
  - **conn.log**: Maps to CIM Network Traffic (e.g., `source`, `dest`, `bytes_in`, `packets_in`, `app`) and ECS Network (e.g., `source.ip`, `destination.ip`, `network.application`).
  - **http.log**: Maps to CIM Web (e.g., `http_method`, `url`, `http_user_agent`) and ECS Web (e.g., `http.request.method`, `url.path`, `http.request.user_agent`).
  - All Zeek fields are preserved in Elasticsearch under `zeek.raw` for unmapped fields.
- **Multiprocessing**: Uses `worker_count` processes (default: CPU core count) for parsing and transformation, with a dedicated sender process for network operations. Suitable for high log rates (e.g., 10,000+ lines/second).
- The connector runs in a separate container (`zeek-connector`) with access to `/var/log/zeek`.
- Disable Splunk or Elasticsearch in `deploy_config.yaml` by setting `enabled: false` if not needed.

## Cleanup
To remove the deployment:
```bash
python3 deploy_zeek.py --config deploy_config.yaml --cleanup
```

## Security Notes
- **Permissions**: Directories use 0750, files use 0644.
- **Password Logging**: Disabled by default (`disable_password_logging: true`).
- **Network Mode**: Uses `host` mode for packet capture, reducing isolation. Use network namespaces for advanced setups.
- **Backups**: Configurations are backed up before deployment to `backup/<timestamp>`.

## Troubleshooting
- **Interface Not Found**: Verify the interface exists:
  ```bash
  ip link show
  ```
- **Deployment Fails**: Check `zeek_deployment.log` for errors.
- **Zeek Crashes**: Run diagnostics:
  ```bash
  docker exec zeek-monitor zeekctl diag
  ```
- **Missing Logs**: Ensure `log_dir` has sufficient space and correct permissions.
- **Prometheus Issues**: Verify `prometheus.yml` and port 9090 accessibility.
- **Connector Issues**: Check `zeek-connector` container logs:
  ```bash
  docker logs zeek-connector
  ```
- **Performance Issues**: Adjust `worker_count`, `batch_size`, or `buffer_timeout` in `deploy_config.yaml` for high log rates.

## Customization
- **ICS Protocols**: Edit `guess_ics_map.txt` for custom protocol mappings.
- **Log Rotation**: Adjust `LogRotationInterval` in `zeekctl.cfg` (default: 24 hours).
- **Cluster Setup**: Enable `cluster.enabled` in `deploy_config.yaml` for multi-node deployments.
- **Metrics**: Extend `prometheus.yml` for additional Zeek metrics.
- **Log Forwarding**: Modify `zeek_connector.py` to support additional log types (e.g., `dns.log`) or custom field mappings.

## Support
Consult https://docs.zeek.org or Zeek community forums for help.