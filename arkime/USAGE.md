# Arkime Deployment with Podman

## Prerequisites

- **Podman** and **Podman Compose** installed.
- **Kubernetes** (optional, for Kubernetes deployment).
- `docker-compose.yml`, `.env`, `Dockerfile`, and `deploy_arkime.py` in the working directory.
- `sudo` privileges for `/etc/hosts` updates and Podman commands.

## Setup

1. **Configure `.env`**:
   - Set `OS_VERSION`, `OS_NODE1`, `OS_JAVA_MEM`, `ARKIME_PORT`, `PCAP_DIR`.
   - Example:
     ```
     OS_VERSION=3
     OS_NODE1=os01
     OS_JAVA_MEM=1g
     ARKIME_PORT=8005
     PCAP_DIR=./pcaps
     ```

2. **Update `Dockerfile`** (if needed):
   - Enable packet capture: `ENV CAPTURE="on"`, `ENV ARKIME_INTERFACE="wlo1"`.
   - Enable Suricata: `ENV SURICATA="on"`.
   - Enable proxy: `ENV PROXY="on"`.
   - Enable WISE: `ENV WISE="on"`.

## Deployment

### Podman Compose
```bash
sudo python3 deploy_arkime.py --mode compose
```

### Kubernetes
```bash
sudo python3 deploy_arkime.py --mode kubernetes --namespace arkime
```

### Cleanup
```bash
sudo python3 deploy_arkime.py --mode compose --cleanup
```

## Access
- **Arkime Viewer**: `http://127.0.0.1:8005`
  - User: `admin`
  - Password: Set in `ARKIME_ADMIN_PASSWORD` (default: `admin`).
- **Logs**: Check `deploy_arkime.log` or `/data/logs/capture.log` (via `podman exec arkime cat /data/logs/capture.log`).

## Notes
- Ensure `PCAP_DIR` exists or will be created.
- For packet capture, verify `ARKIME_INTERFACE` exists (`ip -o link show`).
- Run as `sudo` for `/etc/hosts` updates.