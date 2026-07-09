# LiteLLM

![LiteLLM Logo](https://miro.medium.com/v2/resize:fit:640/format:webp/1*p20EV4wuG9BdQukq14gIcQ.png)

LLM Gateway for model access, logging, and usage tracking across 100+ LLMs in OpenAI format.

## Getting Started

### Prerequisites
- Docker
- Docker Compose
- Git
- Podman (optional for alternative container runtime)
- Kubernetes (optional for orchestration)
- Ansible (optional for automation)
- Python 3.8+ with `pyyaml` and `python-dotenv`
- Redis (for caching)
- Prometheus (for monitoring)

### Setup
1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```
2. Copy `.env.example` to `.env` and add API keys:
   ```bash
   cp .env.example .env
   vim .env
   ```
3. Deploy using the desired platform:
   ```bash
   python deploy.py --platform [docker|podman|kubernetes]
   ```
4. Access the Caddy webserver at `http://localhost:3000` (or your configured `FQDN`).

### Deployment Details
- **Docker/Podman**: Uses `docker-compose.yml` for container orchestration.
- **Kubernetes**: Applies YAMLs in `k8s/` directory, including deployments and ingress.

### Monitoring
- Prometheus metrics are available at `http://localhost:9090` (or configured `PROMETHEUS_PORT`).
- Check service health via healthchecks in `docker-compose.yml`.

### CI/CD
- Automated testing and deployment via GitHub Actions (see `.github/workflows/ci-cd.yml`).
- Push changes to the `main` branch to trigger the pipeline.

### Security
- Use HTTPS in production (enforced via Caddy and Kubernetes Ingress).
- Store API keys in a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault).
- Enable rate limiting and CORS in `Caddyfile`.

## Production Notes
- Use a secrets manager for sensitive data.
- Scale services using Kubernetes for production.
- Monitor with Prometheus and Grafana for production environments.
- Kubernetes deployments are defined in `k8s/`; ensure a valid TLS secret for Ingress.