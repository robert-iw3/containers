# Jira Deployment Stack

This repository provides a Python script to deploy a production-ready Jira stack with PostgreSQL, backups, Wallarm API protection, Traefik proxy, and Prometheus/Grafana monitoring, using Docker, Podman, Kubernetes, or Ansible.

## Prerequisites
- Python 3.x
- For Docker/Podman: `docker` or `podman` and `docker-compose` or `podman-compose` installed
- For Kubernetes: `kubectl` and a Kubernetes cluster
- For Ansible: `ansible`
- Wallarm account (for API security)

## Setup
1. Download files: `main.py`, `env_template.txt`, `docker-compose.yaml`, `prometheus_template.yaml`, `k8s_deployment_template.yaml`, `ansible_playbook_template.yaml`, `jira-api-openapi_template.json`, `requirements.txt`
2. Install Python dependencies: `pip install -r requirements.txt`


## Quick Start
1. Run: `python main.py <type>` where `<type>` is `docker`, `podman`, `kubernetes`, or `ansible`
- Prompts for passwords/tokens (PostgreSQL, Wallarm, Grafana) if `.env` is missing
- Options:
  - `--restore-app`: Restore application data from backup
  - `--restore-db`: Restore database from backup
  - `--configure-monitoring app1:port app2:port`: Add apps to Prometheus monitoring
2. Access Jira at `http://localhost:80` (or configured host/port). Monitor via Grafana at `http://localhost:3000`.
3. For Kubernetes:
- Customize generated manifests in `k8s_manifests` (e.g., set PVCs, update `{metrics_port}`, `{health_path}`, etc.).
- Includes volumes for Jira, PostgreSQL, backups, Traefik, Prometheus, and Grafana.
- Security: Non-root users, restricted filesystem, dropped capabilities.
4. For Ansible:
- Configure `ansible_user` and host inventory.
- Includes security hardening (Docker config, permissions) and monitoring (Prometheus alerts, Grafana datasource).
5. Backups run daily, retaining 7 days. Prometheus monitors failed logins, API anomalies, backup failures, and disk usage.

## Notes
- Ensure `/var/run/docker.sock` is accessible for Docker/Podman.
- Wallarm requires a valid API token; see `env_template.txt`.
- Kubernetes requires pre-created PVCs (e.g., `jira-data-pvc`, `postgres-data-pvc`).
- Prometheus assumes exporters for PostgreSQL/backup metrics; update ports in `prometheus.yml` if needed.