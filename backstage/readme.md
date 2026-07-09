# Backstage Deployment Guide

This guide provides instructions to deploy Backstage on a Kubernetes cluster using an automated Python script.

## Prerequisites
1. **Kubernetes Cluster**: A running Kubernetes cluster (e.g., Minikube, EKS, GKE).
2. **kubectl**: Installed and configured to communicate with your cluster.
3. **Docker**: Installed for building the Backstage image.
4. **Python 3**: Installed with the `kubernetes` and `pyyaml` packages (`pip install kubernetes pyyaml`).
5. **Environment Variables**: Create a `.env` file with the following variables:
   ```
   POSTGRESQL_USERNAME=your_postgres_username
   POSTGRESQL_PASSWORD=your_postgres_password
   POSTGRESQL_DATABASE=backstage
   POSTGRESQL_REPLICATION_USER=your_replication_user
   POSTGRESQL_REPLICATION_PASSWORD=your_replication_password
   GITHUB_TOKEN=your_github_token
   AUTH_GITHUB_CLIENT_ID=your_github_client_id
   AUTH_GITHUB_CLIENT_SECRET=your_github_client_secret
   AUTH_GITHUB_ENTERPRISE_INSTANCE_URL=your_github_enterprise_url
   ```

## Deployment Steps
1. **Clone the Repository**:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Ensure Files are Present**:
   - `Dockerfile`
   - `app-config.yaml`
   - `backstage-deployment.yaml`
   - `deploy_backstage.py`
   - `.env` (with your credentials)

3. **Run the Deployment Script**:
   ```bash
   python3 deploy_backstage.py
   ```

4. **Verify Deployment**:
   ```bash
   kubectl get pods -n backstage
   kubectl port-forward svc/backstage 3000:3000 -n backstage
   ```
   Access Backstage at `http://localhost:3000`.

## Notes
- The deployment creates a `backstage` namespace, a PostgreSQL instance, a Backstage app, and a daily backup CronJob.
- Ensure your Kubernetes cluster has sufficient resources (at least 4Gi memory and 2 CPUs).
- The `backstage-deployment.yaml` file includes a NetworkPolicy to restrict traffic for security.
- Backups are stored in a temporary volume and retained for 7 days.

## Troubleshooting
- Check pod logs: `kubectl logs <pod_name> -n backstage`
- Ensure Docker images are built and accessible.
- Verify `.env` variables are correctly set.