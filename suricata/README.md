# Suricata Deployment Guide

This guide provides instructions to deploy Suricata using a Python deployment script, supporting Docker, Podman, Kubernetes, or Ansible. The setup includes security hardening, performance optimizations, and integration with Splunk and Elasticsearch for log forwarding.

## Prerequisites

- Python 3.9+ with `pydantic`, `pyyaml`, `psutil`, `requests`, `elasticsearch_async`, `aiohttp`, `orjson`, `watchdog`
- One of the following:
  - Docker and `docker-compose`
  - Podman and `podman-compose`
  - Kubernetes (`kubectl`)
  - Ansible (`ansible-playbook`, `community.docker` collection)
- Root or sudo privileges (except for rootless Podman)
- Network interface for packet capture
- 2GB disk space, 4GB memory, 2 CPU cores
- Internet access for pulling images
- (Optional) Splunk instance with HTTP Event Collector (HEC)
- (Optional) Elasticsearch instance (7.x or 8.x)

## File Structure
```console
.
├── deploy_suricata.py                  # Main deployment script for Docker, Podman, Kubernetes, Ansible
├── deploy_config.yaml                  # Configuration file for Suricata and connector settings
├── docker-compose.yml                  # Docker/Podman Compose file for container orchestration
├── Dockerfile                          # Dockerfile for building Suricata container
├── Dockerfile.connector                # Dockerfile for building Suricata connector container
├── entrypoint.sh                       # Entry script for Suricata container
├── logrotate                           # Log rotation configuration for Suricata logs
├── suricata_connector.py               # Script for forwarding logs to Splunk/Elasticsearch
├── suricata-deployment.yaml            # Kubernetes manifest for Suricata deployment
├── suricata-connector-deployment.yaml  # Kubernetes manifest for connector deployment
├── suricata-pvc.yaml                   # Kubernetes manifest for persistent volume claims
├── deploy_suricata.yml                 # Ansible playbook for automated deployment
```

## Deployment Steps

1. **Install Dependencies**
   ```bash
   pip install pyyaml pydantic psutil requests elasticsearch_async aiohttp orjson watchdog
   ```
   For Ansible:
   ```bash
   ansible-galaxy collection install community.docker
   ```

2. **Copy Files**
   Ensure the following files are in your working directory:
   - `deploy_suricata.py`
   - `deploy_config.yaml`
   - `Dockerfile`
   - `docker-compose.yml`
   - `entrypoint.sh`
   - `logrotate`
   - `suricata_connector.py`
   - `Dockerfile.connector`
   - `suricata-deployment.yaml`
   - `suricata-connector-deployment.yaml`
   - `suricata-pvc.yaml`
   - `deploy_suricata.yml`

3. **Configure Deployment**
   Edit `deploy_config.yaml`:
   ```yaml
   suricata:
     version: '8.0.6'
     interface: 'eth0'
     log_dir: '/var/log/suricata'
     rules_dir: '/var/lib/suricata/rules'
     network_mode: 'host'
   security:
     enable_json_logs: true
     disable_password_logging: true
   splunk:
     enabled: false
     hec_url: 'https://your-splunk-host:8088/services/collector/event'
     hec_token: 'your-splunk-hec-token'
   elasticsearch:
     enabled: false
     host: 'http://localhost:9200'
     index: 'suricata-logs'
   deployment:
     method: 'docker'  # Options: docker, podman, kubernetes, ansible
     namespace: 'suricata'
     container_name: 'suricata-monitor'
     kubernetes:
       replicas: 1
       storage_class: 'standard'
       log_storage_size: '10Gi'
   buffer_timeout: 2.0
   worker_count: 4
   batch_size: 50
   ```

4. **Deploy**
   - **Docker**:
     ```bash
     python3 deploy_suricata.py --config deploy_config.yaml
     ```
   - **Podman**:
     ```bash
     python3 deploy_suricata.py --config deploy_config.yaml
     ```
     Ensure `deployment.method: podman`.
   - **Kubernetes**:
     ```bash
     python3 deploy_suricata.py --config deploy_config.yaml
     ```
     Ensure `deployment.method: kubernetes` and `kubectl` configured.
   - **Ansible**:
     ```bash
     ansible-playbook deploy_suricata.yml -e "config_file=deploy_config.yaml"
     ```
     Ensure `deployment.method` matches desired platform.

5. **Verify Deployment**
   - Docker/Podman:
     ```bash
     docker ps  # or podman ps
     ```
   - Kubernetes:
     ```bash
     kubectl get pods -n suricata
     ```
   - Logs:
     ```bash
     ls /var/log/suricata
     ```

6. **Access Suricata Logs**
   Logs in `/var/log/suricata/eve.json` (JSON Lines format) include `flow`, `http`, `alert` events.

## Splunk and Elasticsearch Integration
The `suricata_connector.py` script forwards `eve.json` logs to Splunk (CIM-compliant) and Elasticsearch (ECS-compliant) using multiprocessing.

### Setup
1. **Install Connector Dependencies**
   ```bash
   pip install requests elasticsearch_async aiohttp orjson watchdog
   ```

2. **Configure Splunk**
   - Enable HEC in Splunk.
   - Update `deploy_config.yaml`:
     ```yaml
     splunk:
       enabled: true
       hec_url: 'https://your-splunk-host:8088/services/collector/event'
       hec_token: 'your-splunk-hec-token'
     ```

3. **Configure Elasticsearch**
   - Update `deploy_config.yaml`:
     ```yaml
     elasticsearch:
       enabled: true
       host: 'http://localhost:9200'
       index: 'suricata-logs'
     ```

4. **Tune Performance**
   - `worker_count`: Set to CPU core count (e.g., 4-8).
   - `batch_size`: Use 50 for low latency, 500-1000 for high throughput.
   - `buffer_timeout`: Use 1-2s for Kubernetes, 5-10s for Docker/Podman.

5. **Verify**
   - Splunk: `index=suricata source=suricata:*`
   - Elasticsearch: `curl http://localhost:9200/suricata-logs/_search`
   - Connector logs: `docker logs suricata-connector` or `kubectl logs -n suricata -l app=suricata-connector`

### Notes
- **Field Mappings**:
  - **flow**: CIM Network Traffic (`source`, `dest`, `bytes_in`), ECS Network (`source.ip`, `network.application`).
  - **http**: CIM Web (`http_method`, `url`), ECS Web (`http.request.method`, `url.path`).
  - **alert**: CIM IDS/IPS (`signature`, `severity`), ECS Intrusion Detection (`rule.name`, `event.severity`).
  - All fields in `suricata.raw` (ECS).
- **Performance**: Multiprocessing scales to 10,000+ lines/second.
- **Log Rotation**: Handled by `logrotate` (daily, 200M, 3 rotations).

## Cleanup
```bash
python3 deploy_suricata.py --config deploy_config.yaml --cleanup
```
For Ansible:
```bash
ansible-playbook deploy_suricata.yml -e "config_file=deploy_config.yaml cleanup=true"
```

## Security Notes
- **Permissions**: Files 0644, directories 0750, owned by `suricata` user.
- **Password Logging**: Disabled.
- **Network Mode**: `host` for packet capture (Docker/Podman), `hostNetwork` for Kubernetes.
- **Backups**: Stored in `backup/<timestamp>`.

## Troubleshooting
- **Interface Issues**: `ip link show`
- **Deployment Fails**: Check `docker-compose logs suricata` or `kubectl describe pod -n suricata`
- **Missing Logs**: Verify `/var/log/suricata` permissions and space.
- **Connector Issues**: `docker logs suricata-connector` or `kubectl logs -n suricata -l app=suricata-connector`
- **Performance**: Adjust `worker_count`, `batch_size`, `buffer_timeout`.

## Customization
- **Rules**: Update `/var/lib/suricata/rules`.
- **Log Rotation**: Modify `/etc/logrotate.d/suricata`.
- **Event Types**: Extend `suricata_connector.py` for `dns`, `tls`, etc.

## IDS / IPS mode toggling

The entrypoint selects the data plane from environment variables (defaults =
passive IDS, so existing deployments are unchanged):

| Variable | Values | Purpose |
|---|---|---|
| `IPS_MODE` | `ids` \| `ips` | passive capture vs inline blocking |
| `INLINE_METHOD` | `afpacket_bridge` \| `nfqueue` | how IPS intercepts traffic |
| `CAPTURE_INTERFACE` / `BRIDGE_IFACE_B` | iface names | capture (and bridge B) NIC |
| `RULE_ACTION_POLICY` | `detect` \| `balanced` \| `aggressive` \| `paranoid` | which risk tiers drop vs alert |
| `NFQ_FAIL_OPEN` | `no` \| `yes` | fail-closed vs fail-open on the netfilter queue |

```bash
# passive IDS (default)
docker compose up -d

# inline IPS via NFQUEUE, block high-confidence bad only
IPS_MODE=ips INLINE_METHOD=nfqueue RULE_ACTION_POLICY=balanced docker compose up -d

# two-NIC inline bridge, paranoid (drop everything matched)
IPS_MODE=ips INLINE_METHOD=afpacket_bridge CAPTURE_INTERFACE=eth0 BRIDGE_IFACE_B=eth1 \
  RULE_ACTION_POLICY=paranoid docker compose up -d
```

On start the entrypoint renders `suricata.yaml` from
`templates/suricata.yaml.template` for the selected mode, sets up NFQUEUE
iptables (or the af-packet bridge), and applies the rule action policy via
`scripts/toggle_rule_blocking.py`. `IPS_MODE=ids` always forces every rule back
to `alert` — a passive sensor can never carry drop actions.

The risk tiers map to the shipped rulesets: `docker_malware.rules` and
`salt_typhoon_unc4841.rules` are tier 1 (block-known-bad), so `balanced`+ policies
flip them to `drop`. Extend `TIER_FILES` in the toggle script to tier your own
rule files.

## Custom Rules Configuration

- Place .rules files in ./rules directory
- Place lookup files in ./files directory
- Modify `suricata.yaml` (or the template) to include the custom rules and lookup files. (Examples are for docker_malware and salt_typhoon_unc4841 rulesets)

The `toggle_rule_blocking.py` script will enable active drop for all configured rules in `suricata.yaml`.

The `toggle_rule_blocking.py` script is designed to handle the toggling of rule actions from alert to drop (or vice versa) for you, so you do not need to manually change the rules to drop in the rule files. The script automates this process based on user input, ensuring that the rules in salt_typhoon_unc4841.rules and docker_malware.rules (or any .rules file in /etc/suricata/rules/) are modified as needed.

## Command Examples
Run all commands with `sudo`:
```bash
sudo python3 toggle_rule_blocking.py [options]
```

- **List SIDs**:
  ```bash
  --list
  ```
  Lists SIDs in all `.rules` files in `/etc/suricata/rules/`.

- **Toggle Specific Rule**:
  ```bash
  --sid <SID> --action {alert|drop} [--file <rule_file>]
  ```
  Toggles rule with `<SID>` to `alert` or `drop`. Optional `--file` specifies a rule file (e.g., `salt_typhoon_unc4841.rules`).

- **Toggle All to Drop**:
  ```bash
  --all-drop
  ```
  Sets all `alert` rules in `/etc/suricata/rules/*.rules` to `drop` concurrently.

- **Restore Backup**:
  ```bash
  --restore [--file <rule_file>]
  ```
  Restores rule file(s) from latest backup(s) in `/etc/suricata/rules/backup/`.

## Support
See https://suricata.readthedocs.io or Suricata community forums.