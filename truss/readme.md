# Truss

This project deploys a configurable machine learning model using Truss, Docker/Podman, or Kubernetes, orchestrated with Ansible.

## Prerequisites
- Ansible
- Docker or Podman (for Docker deployment)
- kubectl and Kubernetes cluster (for Kubernetes deployment)
- Python 3.11 with `pyyaml` (`pip install pyyaml`)

## Project Structure
```
ansible_project/
├── ansible-deployment.yml
├── deploy.py
├── roles/
│   └── docker_setup/
│       └── tasks/
│           └── main.yml
├── vars/
│   └── config.yml
├── templates/
│   ├── Dockerfile.j2
│   ├── model.py.j2
│   ├── config.yaml.j2
│   ├── requirements.txt.j2
│   ├── k8s-deployment.yaml.j2
│   └── __init__.py.j2
```

## Configuration
Edit `vars/config.yml` to specify:
- `model_name`: Model identifier (e.g., `meta-llama/Llama-2-7b`).
- `model_requirements`: List of pip packages (e.g., `torch==2.3.0`).
- `python_image_hash`: Python image hash for reproducibility.
- `max_length`: Max tokens for inference (default: 128).
- `pipeline_type`: Pipeline type (e.g., `text-generation`, default: `text-generation`).
- `replicas`: Number of Kubernetes replicas (default: 1).
- `resources`: CPU, memory, and GPU accelerator.
- `use_kubernetes`: Set to `true` for Kubernetes, `false` for Docker.
- `use_podman`: Set to `true` for Podman compatibility.
- Other parameters: `container_name`, `truss_port`, etc.

## Deployment
1. Ensure prerequisites are installed.
2. Configure `vars/config.yml`.
3. Run:
   ```bash
   python3 deploy.py
   ```
   Or specify a custom inventory:
   ```bash
   python3 deploy.py inventory
   ```

## Notes
- Uses non-root user, read-only mounts, and network policies for security.
- Supports any model compatible with Hugging Face `transformers`.
- Includes health checks, auto-scaling, and retry logic.
- For production, add secret management (e.g., Ansible Vault) and persistent storage.