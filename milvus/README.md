# Milvus

Production-style Milvus standalone deployment: etcd (metadata), MinIO
(object storage), Milvus v2.6 with authentication enabled, and the Attu
admin UI. Includes a UAT battery, synthetic data generation, and
application connectors.

## Quick start

```sh
./scripts/bootstrap-env.sh     # writes .env with random credentials
podman-compose up -d
./scripts/smoke-test.sh
```

`milvus-init` (one-shot) rotates the factory-default root password to
`MILVUS_ROOT_PASSWORD` from `.env`. Nothing secret is baked into images;
all credentials live in `.env` (gitignored, chmod 600).

| Service | Container | Exposure |
|---|---|---|
| Milvus gRPC + REST v2 | `milvus-standalone` | `:19530` |
| Milvus metrics/health | `milvus-standalone` | `127.0.0.1:9091` |
| Attu web UI | `milvus-attu` | `127.0.0.1:3001` (log in `root` / `MILVUS_ROOT_PASSWORD`) |
| etcd, MinIO | `milvus-etcd`, `milvus-minio` | internal network only |

## UAT

```sh
./uat/run-uat.sh
```

Containerized pytest battery, two phases:

1. **Functional** — auth (rotated creds accepted, factory default and bad
   creds rejected), RBAC (read-only role can search but not drop),
   collection lifecycle, ingest of a 2000-doc synthetic corpus
   (`uat/corpus.py`, deterministic hashing embedder, no model downloads),
   HNSW index, recall@1 ≥ 0.95, filtered + scalar-range search,
   upsert/delete.
2. **Persistence** — restarts the milvus container, verifies row count
   and search still work.

## Connectors

Start the main stack first, then from `connectors/`:

```sh
podman-compose -f docker-compose.connectors.yml up -d search-api
podman-compose -f docker-compose.connectors.yml run --rm search-api \
    python loader.py --sample 500          # or --file docs.jsonl
curl -s -X POST http://127.0.0.1:8801/search \
    -H 'Content-Type: application/json' \
    -d '{"query":"invoice charged twice","top_k":3,"category":"billing"}'
podman-compose -f docker-compose.connectors.yml run --rm langchain-rag
```

- **search-api** — FastAPI semantic-search microservice
  (`/documents` upsert, `/search` with optional category filter, `/healthz`).
- **loader.py** — batch loader for JSONL corpora or generated sample data.
- **langchain-rag** — LangChain `Milvus` vector-store retriever example.

All connectors share the embedder in `uat/corpus.py`; swap it for a real
embedding model (sentence-transformers, OpenAI, ...) without touching the
Milvus plumbing.

## Operations

- **Backups**: data lives in the `etcd_data`, `minio_data` and
  `milvus_data` named volumes — snapshot those.
- **Monitoring**: Prometheus scrape target on `127.0.0.1:9091/metrics`;
  Grafana dashboards in `deployments/monitor/`.
- **TLS / RBAC / multi-DB**: see [tls.md](tls.md), [rbac.md](rbac.md),
  [create-db.md](create-db.md), [connect.md](connect.md),
  [enable-auth.md](enable-auth.md).
- **Kubernetes**: `k8s.sh` (helm standalone install); upstream deployment
  variants under `deployments/`.
- **Building Milvus from source**: vendored upstream tooling in `build/`
  (uses `build/docker-compose-builder.yml`).
