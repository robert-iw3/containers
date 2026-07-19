# pgvector

Production-style PostgreSQL 17 + pgvector 0.8 deployment with
least-privilege application roles, a tuned server, and a documents
schema with an HNSW cosine index. Includes a UAT battery, synthetic
data generation, and application connectors.

## Quick start

```sh
./scripts/bootstrap-env.sh     # writes .env with random passwords
podman-compose up -d
./scripts/smoke-test.sh
```

First boot runs `init/01-init.sh`: `CREATE EXTENSION vector`, the
`documents` table (`vector(384)` embedding column), an HNSW cosine index,
and two application roles — `app_rw` (SELECT/INSERT/UPDATE/DELETE) and
`app_ro` (SELECT only). All passwords live in `.env` (gitignored,
chmod 600).

| Service | Container | Exposure |
|---|---|---|
| PostgreSQL | `pgvector-main` | `127.0.0.1:5433` (container port 5432) |

Note: the official image trusts loopback connections from *inside* the
container; anything on the network path authenticates with scram. The
smoke test exercises the network path.

## UAT

```sh
./uat/run-uat.sh
```

Containerized pytest battery, two phases:

1. **Functional** — auth (bad password rejected), extension + HNSW index
   present, binary-`COPY` ingest of a 2000-doc synthetic corpus
   (`uat/corpus.py`, deterministic hashing embedder, no model
   downloads), recall@1 ≥ 0.95, an `EXPLAIN` check proving the HNSW
   index is used, filtered + scalar-range search, update/delete, and
   role separation (`app_ro` can query but not write).
2. **Persistence** — restarts the postgres container, verifies row count
   and search still work.

## Connectors

Start the main stack first, then from `connectors/`:

```sh
podman-compose -f docker-compose.connectors.yml up -d search-api
podman-compose -f docker-compose.connectors.yml run --rm search-api \
    python loader.py --sample 500          # or --file docs.jsonl
curl -s -X POST http://127.0.0.1:8803/search \
    -H 'Content-Type: application/json' \
    -d '{"query":"invoice charged twice","top_k":3,"category":"billing"}'
podman-compose -f docker-compose.connectors.yml run --rm langchain-rag
```

- **search-api** — FastAPI semantic-search microservice running as
  `app_rw` (`/documents` upsert, `/search` with optional category
  filter, `/healthz`).
- **loader.py** — batch loader for JSONL corpora or generated sample data.
- **langchain-rag** — LangChain `PGVector` retriever example
  (langchain-postgres).

All connectors share the embedder in `uat/corpus.py`; swap it for a real
embedding model (sentence-transformers, OpenAI, ...) without touching
the SQL.

## Operations

- **Backups**: standard postgres tooling (`pg_dump`, WAL archiving);
  data lives in the `pgvector_data` named volume.
- **Tuning**: server flags are set in the compose `command`
  (shared_buffers, work_mem, maintenance_work_mem for index builds,
  max_wal_size). Adjust to the host; `hnsw.ef_search` can be set
  per-session for recall/latency trade-offs.
- **Scaling**: single node; use streaming replication or a managed
  postgres for HA — the schema and roles carry over unchanged.
