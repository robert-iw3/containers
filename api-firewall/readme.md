# Wallarm API Firewall Deployment

This project deploys the Wallarm API Firewall to protect any API using an OpenAPI JSON specification. It supports Docker, Podman, Kubernetes, and Ansible deployments.

## Prerequisites
- Python 3.8+
- Tools: Docker or Podman, kubectl (for Kubernetes), Ansible, kompose (for Kubernetes)
- Python packages: `pip install docker kubernetes ansible-runner requests pyyaml`
- An OpenAPI JSON specification file (e.g., `openapi_spec.json`)

## Structure
```console
.
├── config/
│   ├── config.yaml
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   ├── coraza.conf
│   ├── allowed.iplist.db
│   ├── entrypoint.sh
│   ├── api-fw-csr.conf
│   ├── ca-csr.conf
│   ├── deploy.yml
├── openapi_spec.json
├── deploy_api_firewall.py
├── README.md
```

## Setup
1. **Prepare Directory Structure**:
   - Place your OpenAPI JSON file (e.g., `openapi_spec.json`) in the project directory.
   - Ensure all configuration files are in the `config` directory (see `config/config.yaml` for paths).

2. **Customize Configuration**:
   - Edit `config/config.yaml`:
     - Set `openapi_spec` to your OpenAPI JSON filename.
     - Update `server_url` to your API's URL (e.g., `http://your-api:port`).
     - Adjust `api_fw_url` and ports as needed.
   - Modify `config/allowed.iplist.db` for allowed IPs.
   - Update `config/api-fw-csr.conf` and `config/ca-csr.conf` for SSL settings if needed.

3. **Deploy the API Firewall**:
   ```bash
   python3 deploy_api_firewall.py --config-file config/config.yaml --deploy-type docker --verbose
   ```
   - Options: `--deploy-type` (`docker`, `kubernetes`, `ansible`), `--verbose` for logs.

4. **Test the Deployment**:
   - Send a request that violates the OpenAPI spec (e.g., wrong parameter type) to `http://127.0.0.1:8080`.
   - Check logs: `podman-compose logs -f` (Docker/Podman) or `kubectl logs <pod-name>` (Kubernetes).
   - Expect an ERROR message for non-compliant requests.

5. **Enable Traffic**:
   - Update your application's Ingress, NGINX, or load balancer to route traffic through the API Firewall (`127.0.0.1:8080`).

## Notes
- Ensure all files in `config` are present and `entrypoint.sh` is executable (`chmod +x config/entrypoint.sh`).
- For Kubernetes, `kompose` converts `docker-compose.yaml` to manifests.
- See `config/coraza.conf` for ModSecurity rule customization.