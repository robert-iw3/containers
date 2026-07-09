# Snyk Scanner

## Overview
This tool provides a Python script to scan local or remote code bases and JAR files using Snyk inside a Docker container. It supports multi-directory scanning, remote codebase download, Snyk best practices like --all-projects and --severity-threshold, optimized JAR scanning with per-file monitoring, and HTML report generation.

## Prerequisites
- Docker or Podman installed.
- Snyk account and API token (SNYK_TOKEN environment variable).
- For Kubernetes: kubectl and a cluster.
- For Ansible: ansible installed.

## Usage

### Build the Docker Image
```bash
docker build -t snyk-scanner .

docker run --rm \
  -v /local/codebase1:/scan/dir1 \
  -v /local/codebase2:/scan/dir2 \
  -v /local/jars:/scan/jars \
  -v /local/reports:/reports \
  -e SNYK_TOKEN=your-token \
  snyk-scanner \
  --token=$SNYK_TOKEN \
  --dirs=/scan/dir1,/scan/dir2 \
  --jar-dirs=/scan/jars \
  --remote-repo-url=your-snyk-project-name \
  --url=https://example.com/codebase.zip \
  --code-name=myproject \
  --html-output-dir=/reports \
  --severity-threshold=high \
  --monitor  # Optional: Upload to Snyk

# Run with Podman
# Similar to Docker, replace docker with podman.

# Deploy with Kubernetes

# Build and push the image to a registry.
# Create a secret:

kubectl create secret generic snyk-secret --from-literal=token=your-token

# Adjust volume paths in deploy.yaml; use emptyDir or PVC for reports.

# Apply:

kubectl apply -f deploy.yaml

# Run with Ansible

# Adjust paths and vars in playbook.yaml.

# Run:
ansible-playbook playbook.yaml
```