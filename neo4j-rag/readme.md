# Neo4j GraphRAG

A production-ready Retrieval-Augmented Generation stack built on a **Neo4j**
knowledge graph and local LLMs (**Ollama**), fronted by **OpenWebUI** with
**Keycloak** single sign-on over TLS.

The whole stack lives in [`stack/`](stack/) — start there:

- **[stack/README.md](stack/README.md)** — architecture, security posture,
  quick start, and the local end-to-end test.

```
browser ─TLS→ traefik ─┬──→ open-webui   (native OIDC relying party → keycloak)
                       └──→ keycloak     (login UI + token endpoint)

open-webui ──OpenAI API──→ graphrag ──→ neo4j    (graph + vector store)
                                    └──→ ollama  (local LLM + embeddings)
```

## Layout

```
neo4j-rag/
├── stack/                 production stack (compose, configs, service, docs)
│   ├── docker-compose.yml
│   ├── stack.yaml         single source of truth (hosts, images, secrets)
│   ├── .env.example
│   ├── graphrag/          OpenAI-compatible Neo4j RAG service (LangChain 1.x)
│   ├── keycloak/          realm template (OpenWebUI OIDC client)
│   ├── postgres/          hardened postgresql.conf + pg_hba.conf
│   ├── traefik/           TLS + security-headers dynamic config
│   ├── ollama/            model-puller init script
│   ├── scripts/render.sh  renders .env + realm from stack.yaml
│   ├── uat/run-uat.sh     full TLS + real-OIDC smoke test
│   └── ansible/           single-host podman-compose deployment
├── images/                data-model diagram
└── archive/               superseded implementations (see below)
```

## Quick start

```bash
cd stack
scripts/render.sh                      # generate .env + Keycloak realm
# add TLS material to the path in stack.yaml (stack.tls_dir)
podman-compose -p neo4j-stack --env-file .env -f docker-compose.yml up -d
```

To try it locally end-to-end (self-signed CA, `*.localhost` hosts):

```bash
cd stack && uat/run-uat.sh            # tear down with: uat/run-uat.sh --down
```
