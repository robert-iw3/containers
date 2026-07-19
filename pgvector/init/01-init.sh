#!/bin/bash
# First-boot provisioning: pgvector extension, documents schema with an
# HNSW cosine index, and least-privilege application roles. Passwords
# come from the environment (.env) — nothing is baked into the image.
set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<EOF
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id        bigint PRIMARY KEY,
    text      text NOT NULL,
    category  text NOT NULL,
    year      int,
    embedding vector(384) NOT NULL
);

CREATE INDEX documents_embedding_idx ON documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
CREATE INDEX documents_category_idx ON documents (category);

CREATE ROLE app_rw LOGIN PASSWORD '${APP_RW_PASSWORD}';
CREATE ROLE app_ro LOGIN PASSWORD '${APP_RO_PASSWORD}';

GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO app_rw, app_ro;
GRANT USAGE ON SCHEMA public TO app_rw, app_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO app_rw;
GRANT SELECT ON documents TO app_ro;
EOF
