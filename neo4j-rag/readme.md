# Neo4j GenAI Stack RAG Application Deployment Guide

## File Structure
```
.
├── ansible/
│   ├── deploy.yml
│   ├── hosts.ini
│   ├── group_vars/
│   │   └── all.yml
│   └── roles/
│       ├── common/
│       │   └── tasks/main.yml
│       ├── neo4j/
│       │   └── tasks/main.yml
│       ├── ollama/
│       │   └── tasks/main.yml
│       ├── bot/
│       │   └── tasks/main.yml
│       ├── pdf_bot/
│       │   └── tasks/main.yml
│       ├── loader/
│       │   └── tasks/main.yml
│       ├── api/
│       │   └── tasks/main.yml
│       └── front-end/
│           └── tasks/main.yml
├── templates/
│   ├── docker-compose.yml.j2
│   ├── Dockerfile.j2
│   ├── k8s-deployment.yml
│   ├── k8s-service.yml
│   ├── k8s-configmap.yml
│   ├── k8s-hpa.yml
│   ├── k8s-rbac.yml
│   ├── k8s-secret.yml
│   └── k8s-ingress.yml
├── front-end/
│   └── [your front-end files, e.g., package.json, src/]
├── images/
│   └── datamodel.png
├── api.py
├── bot.py
├── chains.py
├── loader.py
├── pdf_bot.py
├── utils.py
├── pull_model.clj
├── requirements.txt
├── .env.example
├── install_ollama.py
├── install_ollama.sh
├── nginx.conf
├── pull_model.Dockerfile
├── front-end.Dockerfile
├── tests/
│   └── test_chains.py
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── deploy.py
└── data/
```

## Deployment Steps

1. **Clone and Configure**:
   ```
   git clone <repo-url>
   cd neo4j-genai-stack
   cp .env.example .env
   # Edit .env: Set NEO4J_URI, NEO4J_PASSWORD, LLM, EMBEDDING_MODEL, IMAGE_REGISTRY (for K8s)
   ```

2. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Deploy**:
   - **Docker**:
     ```
     python deploy.py --orchestrator docker --env-file .env
     ```
   - **Kubernetes**:
     ```
     # Ensure kubectl configured and cluster ready
     python deploy.py --orchestrator kubernetes --env-file .env --extra-vars "replicas=1 IMAGE_REGISTRY=your-registry:5000"
     # Verify: kubectl get pods,services
     # Access: kubectl port-forward svc/bot 8501:8501
     ```

4. **Load Data** (if needed):
   Access loader at http://localhost:8502 and import StackOverflow tags.

5. **Access Services**:
   - Neo4j: http://localhost:7474
   - Bot: http://localhost:8501
   - PDF Bot: http://localhost:8503
   - Loader: http://localhost:8502
   - API: http://localhost:8504/docs
   - Front-end: http://localhost:8505