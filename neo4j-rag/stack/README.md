# Neo4j GraphRAG stack — OpenWebUI + Keycloak SSO

A production-oriented Retrieval-Augmented Generation stack: a Neo4j knowledge
graph and local LLMs (Ollama) fronted by **OpenWebUI**, with all user access
gated by **Keycloak** single sign-on over TLS.

```
browser ─TLS→ traefik ─┬──→ open-webui   (native OIDC relying party → keycloak)
                       └──→ keycloak     (login UI + token endpoint)

open-webui ──OpenAI API──→ graphrag ──→ neo4j    (graph + vector store)
                                    └──→ ollama  (local LLM + embeddings)
```

OpenWebUI authenticates users directly against Keycloak (OpenID Connect) and
consumes the **Neo4j GraphRAG** service as an OpenAI-compatible model provider.
GraphRAG exposes two selectable models:

| model            | behaviour                                             |
| ---------------- | ----------------------------------------------------- |
| `neo4j-graphrag` | vector search over the graph, expanded to top answers |
| `neo4j-llm`      | the same LLM with no retrieval (baseline)             |

## Services

| service        | image                              | role                                   | host port |
| -------------- | ---------------------------------- | -------------------------------------- | --------- |
| `traefik`      | traefik:v3.7.8                     | TLS reverse proxy (single entrypoint)  | `${TLS_PORT}` |
| `keycloak`     | keycloak:26.7.0                    | OIDC identity provider (realm import)  | via proxy |
| `keycloak-db`  | postgres:17.10-alpine              | Keycloak database (SCRAM)              | internal  |
| `open-webui`   | open-webui:main                    | chat UI, Keycloak OIDC relying party   | via proxy |
| `openwebui-db` | postgres:17.10-alpine              | OpenWebUI database (SCRAM)             | internal  |
| `graphrag`     | built from `graphrag/`             | OpenAI-compatible Neo4j RAG API        | internal  |
| `neo4j`        | neo4j:5.26                         | graph + vector store (apoc)            | internal  |
| `ollama`       | ollama/ollama:latest               | local LLM + embedding runtime          | internal  |
| `pull-model`   | alpine:3.21                        | one-shot: pulls the chat/embed models  | –         |
| `loader`       | built from `graphrag/`             | one-shot StackOverflow importer (`--profile load`) | – |
| `backups`      | postgres:17.10-alpine              | nightly pg_dump of both databases      | –         |

Only traefik publishes a host port. Neo4j, Ollama, GraphRAG and the databases
are reachable only on the private container network.

## Security posture

- **TLS everywhere at the edge**; one published host:port so the Keycloak
  issuer URL is identical for the browser and OpenWebUI's back-channel.
- **SSO-only** — OpenWebUI's local login form is disabled; identities and the
  admin role come from Keycloak (realm role `admin` → OpenWebUI admin).
- **PostgreSQL** with SCRAM-SHA-256 and access scoped to the stack subnet;
  no `trust`/`peer` shortcut (`postgres/pg_hba.conf`).
- `no-new-privileges`, pinned images, non-root GraphRAG, capability-dropped
  Ollama, log rotation, and per-request `secure-headers`.
- Secrets live only in the gitignored `.env`; the GraphRAG API requires a
  bearer token.
- OpenWebUI trusts the stack CA for its OIDC back-channel (appended to certifi
  at start-up) rather than disabling TLS verification.

## Quick start

```bash
# 1. Configure — edit stack.yaml (hosts, models), then render .env + realm.
#    Blank secrets in stack.yaml are generated and saved to .env on first run.
scripts/render.sh

# 2. Provide TLS material in stack.tls_dir (tls.crt, tls.key, ca.crt).
#    For real certs, ca.crt may be your internal CA or omitted for public CAs.

# 3. Bring the stack up.
podman-compose -p neo4j-stack --env-file .env -f docker-compose.yml up -d

# 4. Load some data into the graph (optional; one-shot).
podman-compose -p neo4j-stack --env-file .env -f docker-compose.yml \
  --profile load run --rm loader --tag neo4j --pages 1
```

Then browse to `https://${APP_HOST}:${TLS_PORT}`, sign in through Keycloak, and
pick the `neo4j-graphrag` model.

### Local end-to-end test

`uat/run-uat.sh` provisions a local CA, generates `.env` with `*.localhost`
hostnames, brings the stack up in stages, and asserts the Keycloak import, the
GraphRAG API, OpenWebUI health, and a full Keycloak→OpenWebUI login. Tear down
with `uat/run-uat.sh --down`.

## Configuration

`stack.yaml` is the single source of truth (`scripts/render.sh` and the Ansible
playbook read it). Key knobs:

- `models.llm` — any Ollama tag (auto-pulled) or an OpenAI/Bedrock id.
- `models.embedding_model` — `sentence_transformer` (in-process, no key),
  `ollama`, `openai`, or `aws`. **Changing this changes the vector dimension**;
  drop the `stackoverflow` index and re-load if you switch.
- `models.rag_search_type` — `vector` or `hybrid` (adds the fulltext index).

Hosted providers (OpenAI/Google/AWS) need their API keys added to `.env`.

## Administration

```bash
# Neo4j has no host port; use cypher-shell inside the container.
podman exec -it neo4j-neo4j-stack cypher-shell -u neo4j -p "$NEO4J_PASSWORD"

# GraphRAG readiness.
podman exec graphrag-neo4j-stack curl -s http://localhost:8504/health
```

Backups land in the `backups` volume (`keycloak-*.sql.gz`,
`openwebui-*.sql.gz`, 7-day retention). Neo4j data lives in the `neo4j-data`
volume — snapshot it or use `neo4j-admin database dump` for offline backups.
