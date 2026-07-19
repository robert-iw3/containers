# Weaviate

Production-style single-node Weaviate v1.38 deployment with API-key
authentication (admin + read-only identities), persistence, and
Prometheus metrics. Includes a UAT battery, synthetic data generation,
and application connectors.

## Quick start

```sh
./scripts/bootstrap-env.sh     # writes .env with random API keys
podman-compose up -d
./scripts/smoke-test.sh
```

Anonymous access is disabled; every request needs one of the two API
keys from `.env` (gitignored, chmod 600). The `admin` identity has full
access, `readonly` can only query.

| Service | Container | Exposure |
|---|---|---|
| REST API | `weaviate-main` | `:8080` |
| gRPC (used by v4 clients) | `weaviate-main` | `:50051` |
| Prometheus metrics | `weaviate-main` | `127.0.0.1:2112` |

## UAT

```sh
./uat/run-uat.sh
```

Containerized pytest battery, two phases:

1. **Functional** — auth (admin accepted; anonymous, bad key rejected;
   read-only key can query but not create collections), collection
   lifecycle, ingest of a 2000-doc synthetic corpus (`uat/corpus.py`,
   deterministic hashing embedder, no model downloads) with
   self-provided vectors, HNSW cosine index, recall@1 ≥ 0.95, filtered +
   scalar-range search, update/delete.
2. **Persistence** — restarts the weaviate container, verifies the
   object count and search still work.

## Connectors

Start the main stack first, then from `connectors/`:

```sh
podman-compose -f docker-compose.connectors.yml up -d search-api
podman-compose -f docker-compose.connectors.yml run --rm search-api \
    python loader.py --sample 500          # or --file docs.jsonl
curl -s -X POST http://127.0.0.1:8802/search \
    -H 'Content-Type: application/json' \
    -d '{"query":"invoice charged twice","top_k":3,"category":"billing"}'
podman-compose -f docker-compose.connectors.yml run --rm langchain-rag
```

- **search-api** — FastAPI semantic-search microservice
  (`/documents` upsert, `/search` with optional category filter, `/healthz`).
- **loader.py** — batch loader for JSONL corpora or generated sample data.
- **langchain-rag** — LangChain `WeaviateVectorStore` retriever example.

All connectors share the embedder in `uat/corpus.py`; swap it for a real
embedding model (sentence-transformers, OpenAI, ...) without touching
the Weaviate plumbing.

## Operations

- **Backups**: data lives in the `weaviate_data` named volume — snapshot
  it, or configure a `backup-*` module for native backups.
- **Monitoring**: Prometheus scrape target on `127.0.0.1:2112/metrics`.
- **Scaling**: this is a single node (`CLUSTER_HOSTNAME=node1`); for HA
  use the raft-based multi-node setup or the official helm chart.
- **Modules**: `ENABLE_MODULES` is empty and the vectorizer is `none` —
  vectors are supplied by the application, so no model containers or
  external API keys are required. Add `text2vec-*` modules there if you
  want server-side vectorization.
