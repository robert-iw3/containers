# Apache Flink 2.0.0 Deployment Guide

This project provides a Python-driven automated deployment of Apache Flink 2.0.0 using Docker/Podman, Kubernetes, and Ansible. It focuses on security, maintainability, optimization, and performance.

## Prerequisites

- Python 3.7+
- Docker (with BuildKit enabled) or Podman
- Kubernetes cluster (minikube or a managed cluster)
- kubectl
- Ansible
- Java 21
- 8GB RAM minimum (16GB recommended)
- TLS certificates (if `enable_tls` is true)

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd flink-deployment
   ```

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate TLS Certificates (if enabling TLS)**
   Generate `keystore.jks` and `truststore.jks` using Java's `keytool`:
   ```bash
   keytool -genkeypair -alias flink -keyalg RSA -validity 365 -keystore keystore.jks -storepass password
   keytool -export -alias flink -keystore keystore.jks -rfc -file flink.cert
   keytool -import -alias flink -file flink.cert -keystore truststore.jks -storepass password
   ```
   Place the certificates in the directory specified in `flink_config.yaml` under `security.cert_path` (e.g., `/path/to/certs`).

4. **Configure Deployment**
   Edit `flink_config.yaml` to customize:
   - Flink version
   - Namespace
   - Container engine (docker/podman)
   - Memory and CPU settings
   - Security (TLS) and monitoring options
   - Update `cert_path` to the actual path containing `keystore.jks` and `truststore.jks`

5. **Build and Deploy**
   Enable Docker BuildKit for optimized builds:
   ```bash
   export DOCKER_BUILDKIT=1
   python deploy_flink.py --config flink_config.yaml
   ```

6. **Verify Deployment**
   - Access Flink UI: `http://<cluster-ip>:8081` (or `https://<cluster-ip>:8081` if TLS is enabled)
   - Check pod status: `kubectl get pods -n flink`
   - View logs: `kubectl logs -n flink -l app=flink`
   - Verify healthcheck: `kubectl exec -n flink <pod-name> -- curl -f http://localhost:8081`

## Troubleshooting

- Check logs: `kubectl logs -n flink <pod-name>`
- Verify services: `kubectl get svc -n flink`
- Check health status: `kubectl describe pod -n flink <pod-name>`
- Review Ansible logs in `ansible-runner/artifacts`

## Stopping the Cluster

```bash
kubectl delete namespace flink
```

## References

- [Apache Flink Documentation](https://flink.apache.org/)
- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Ansible Documentation](https://docs.ansible.com/)
- [Docker BuildKit](https://docs.docker.com/build/buildkit/)