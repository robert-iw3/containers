# Cribl Deployment Guide

## Overview
This repository deploys Cribl LogStream (master-workers architecture) using Ansible and Python, with support for Kubernetes, Docker, or Podman. It is optimized for scalability, security, and integrations with Splunk (HEC/S2S) and Elastic (HTTP/Beats). Improvements include enhanced QA checks, secure secret management, and dynamic resource allocation.

## Prerequisites
- **Tools**:
  - Ansible with collections: `kubernetes.core`, `community.docker`, `community.general` (install via `ansible-galaxy collection install kubernetes.core community.docker community.general`)
  - Python 3.6+
  - Platform-specific: `kubectl` (Kubernetes), `docker`/`docker-compose` (Docker), `podman` (Podman), `yamllint` (for QA)
- **Files**:
  - `./certs/client.pem`: Valid SSL certificate for Splunk integration (replace placeholder)
  - `.env`: Optional environment file for overrides (e.g., `SPLUNK_HOST=splunk:9997`, `ELASTIC_HOST=elastic:9200`, `SPLUNK_HEC_TOKEN=your-token`, `ELASTIC_API_KEY=your-key`)
- **Integrations**:
  - Running Splunk instance (default port 9997 for S2S, 8088 for HEC)
  - Running Elasticsearch instance (default port 9200)
- **Kubernetes**:
  - Storage class `fast-ssd` (or modify `cribl-k8s.yaml` to match your cluster’s storage class)
  - Valid kubeconfig for cluster access

## Deployment
1. **Clone Repository**:
   ```bash
   git clone this repo
   cd cribl
   ```

2. **Install Dependencies and Prepare Host**:
   ```bash
   sudo bash prep_cribl_host.sh

   ansible-galaxy collection install kubernetes.core community.docker community.general
   ```

3. **Prepare Certificates**:
   - Place a valid `client.pem` in `./certs/` for Splunk SSL.
   - See `generate_cert.py` as an example
   - Optionally, create `.env` with integration credentials:
     ```bash
     echo "SPLUNK_HOST=splunk:9997" >> .env
     echo "ELASTIC_HOST=elastic:9200" >> .env
     echo "SPLUNK_HEC_TOKEN=your-splunk-hec-token" >> .env
     echo "ELASTIC_API_KEY=your-elastic-api-key" >> .env
     ```

4. **Run Deployment**:
   ```bash
   python deploy_cribl.py --platform kubernetes --replicas 3 --splunk_host splunk:9997 --elastic_host elastic:9200 --splunk_hec_token your-token --elastic_api_key your-key --verbose

   # scalable
   python deploy_cribl.py --platform kubernetes --data-volume 25000 --reduction-factor 0.4 --cpus-per-worker 8 --splunk_host splunk:9997 --elastic_host elastic:9200 --splunk_hec_token your-token --elastic_api_key your-key --verbosew
   ```
   - Options:
     - `--platform`: `kubernetes`, `docker`, or `podman`
     - `--replicas`: Number of worker nodes (default: 2)
     - `--namespace`: Kubernetes namespace (default: `default`)
     - `--splunk_host`, `--elastic_host`: Override default endpoints
     - `--splunk_hec_token`, `--elastic_api_key`: Authentication tokens
     - `--dry-run`: Run QA checks without applying changes
     - `--verbose`: Detailed Ansible output

5. **Access Cribl UI**:
   - **Kubernetes**: `kubectl -n default port-forward svc/cribl-master 19000:9000`, then open `http://localhost:19000`
   - **Docker/Podman**: Open `http://localhost:19000`
   - Default credentials: `admin/admin` (change in production)

## Integrations
| System  | Protocol   | Endpoint                     | Cribl UI Setup                                      |
|---------|------------|------------------------------|----------------------------------------------------|
| Splunk  | HEC/S2S    | `<splunk_host>:9997` or `workers:9999` | Sources: Syslog/HEC → Pipelines → Destinations: Splunk (use HEC token) |
| Elastic | HTTP/Beats | `<elastic_host>:9200` or `workers:10200` | Sources: Beats/HTTP → Pipelines → Destinations: Elastic (use API key) |

### Steps to Configure Integrations
1. Login to Cribl UI (`http://localhost:19000`, `admin/admin`).
2. Add a Source (e.g., Syslog on port 5140 or HEC on 10088).
3. Create a Pipeline for data transformation (optional).
4. Add a Destination:
   - **Splunk**: Configure Splunk destination with HEC token or SSL cert.
   - **Elastic**: Configure Elastic destination with API key or basic auth.
5. Test connectivity in Cribl UI under Destinations > Status.

## Scaling
- **Kubernetes**: Workers auto-scale via Horizontal Pod Autoscaler (HPA) based on CPU (70%) and memory (80%). Adjust `cribl_hpa_max` in `deploy_cribl.yml`.
- **Docker**: Scale workers with `docker compose up --scale workers=2`. Note: Port conflicts may occur; use Docker Swarm or Traefik for production.
- **Podman**: Workers use port offsets (e.g., `99991` for Splunk on worker-1). Scale via `--replicas`.

## Troubleshooting
- **View Logs**:
  - Kubernetes: `kubectl logs -n default -l app=cribl-master`
  - Docker: `docker logs master`
  - Podman: `podman logs master`
- **Health Checks**: Deployment verifies `/api/v1/health`. Check integration status via `/api/v1/system/destinations`.
- **Integration Issues**:
  - Verify Splunk/Elastic endpoints: `curl <splunk_host>:9997` or `curl <elastic_host>:9200/_cluster/health`
  - Ensure tokens/keys are correct in `.env` or Secrets.
- **Port Conflicts**: For Docker/Podman scaling, adjust port mappings in `docker-compose.yml` or Podman tasks.
- **Storage Issues**: Ensure `fast-ssd` storage class exists (Kubernetes) or local volumes are accessible (Docker/Podman).

## FAQ
- **Why am I seeing port conflicts in Docker/Podman?**
  - Scaling on a single host reuses ports (e.g., 9999). Use port offsets (Podman) or a reverse proxy like Traefik (Docker).
- **How do I secure the deployment?**
  - Replace `client.pem` with a valid cert, store tokens in a vault, change default Cribl credentials, and apply Kubernetes NetworkPolicies.
- **How do I monitor Cribl?**
  - Prometheus scraping is enabled (port 9000). Set up Prometheus/Grafana for metrics.

## Notes
- **Security**: Replace placeholder `client.pem`, secure `CRIBL_DIST_TOKEN` (e.g., via HashiCorp Vault), and update default credentials.
- **Production**: Use Cribl’s official Helm charts directly and integrate with a secret management system.
- **Monitoring**: Prometheus annotations are included in Kubernetes manifests. Deploy Prometheus/Grafana for full observability.