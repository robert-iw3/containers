<p align="center">
  <img src="https://qdrant.tech/articles_data/qdrant-1.3.x/web-ui.png" width="800" />
</p>

Qdrant - High-performance, massive-scale Vector Database for the next generation of AI.

# Qdrant Deployment Automation

This project automates the deployment of Qdrant with Kafka integration using Ansible and Podman or Kubernetes.

## Prerequisites
- Python 3.8+
- Ansible (`pip install ansible`)
- Podman and podman-compose (`sudo apt-get install podman podman-compose` or equivalent)
- Kubernetes cluster (if using Kubernetes deployment)
- SSH access to target host(s) with key-based authentication
- Environment variables:
  - `QDRANT_API_KEY`: Secure API key for Qdrant
  - `GRAFANA_ADMIN_PASSWORD`: Grafana admin password (default: admin)

## Deployment Instructions

### Using Ansible with Podman
1. Clone this repository.
2. Edit `deploy_config.yml` to specify your target host(s) and configuration.
3. Run the deployment script:
   ```bash
   python deploy_qdrant.py --config deploy_config.yml
   ```
4. Verify deployment:
   - Qdrant: `http://<host>:6333/readyz`
   - Grafana: `http://<host>:3000`
   - Prometheus: `http://<host>:9090`

### Using Kubernetes
1. Clone this repository.
2. Apply the Kubernetes configuration:
   ```bash
   kubectl apply -f kubernetes-deployment.yml
   ```
3. Verify deployment:
   - Check pod status: `kubectl get pods`
   - Access services via configured NodePorts or Ingress

## Configuration
- `deploy_config.yml`: Update `hosts`, `qdrant_version`, `kafka_version`, `data_dir`, and `tls_enabled` as needed.
- Kubernetes: Modify `kubernetes-deployment.yml` for custom configurations (e.g., storage, replicas).

## Notes
- Ensure firewall ports (6333, 6334, 9092, 9090, 3000) are open.
- TLS certificates are auto-generated; replace with production certificates if needed.
- Logs are saved to `deployment_*.log` in the project directory.