"""
Semantic-search REST service backed by PostgreSQL + pgvector.

Endpoints:
  GET  /healthz                     liveness + row count
  POST /documents [{id,text,category}]   embed + upsert
  POST /search {query, top_k, category}  cosine search, optional filter

Runs as the least-privilege app_rw role. Embeddings come from
corpus.embed (deterministic hashing embedder). Swap embed() for a real
model (e.g. sentence-transformers) in production; everything else stays
the same.
"""

import os

import numpy as np
import psycopg
from fastapi import FastAPI
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from corpus import embed

HOST = os.environ.get("PGHOST", "pgvector")
DB = os.environ["POSTGRES_DB"]
RW_PASSWORD = os.environ["APP_RW_PASSWORD"]

pool = ConnectionPool(
    conninfo=f"host={HOST} port=5432 dbname={DB} user=app_rw password={RW_PASSWORD}",
    min_size=1,
    max_size=8,
    configure=register_vector,
    kwargs={"autocommit": True},
)

app = FastAPI(title="pgvector-semantic-search")


class Document(BaseModel):
    id: int
    text: str
    category: str = "general"


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    category: str | None = None


@app.get("/healthz")
def healthz():
    with pool.connection() as conn:
        count = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
    return {"status": "ok", "table": "documents", "count": count}


@app.post("/documents")
def add_documents(docs: list[Document]):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO documents (id, text, category, embedding) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET "
                "text = EXCLUDED.text, category = EXCLUDED.category, "
                "embedding = EXCLUDED.embedding",
                [
                    (d.id, d.text, d.category, np.array(embed(d.text)))
                    for d in docs
                ],
            )
    return {"upserted": len(docs)}


@app.post("/search")
def search(req: SearchRequest):
    where = "WHERE category = %(category)s" if req.category else ""
    with pool.connection() as conn:
        rows = conn.execute(
            f"SELECT id, text, category, 1 - (embedding <=> %(q)s) AS score "
            f"FROM documents {where} "
            f"ORDER BY embedding <=> %(q)s LIMIT %(k)s",
            {
                "q": np.array(embed(req.query)),
                "k": req.top_k,
                "category": req.category,
            },
        ).fetchall()
    return {
        "hits": [
            {"id": r[0], "text": r[1], "category": r[2], "score": float(r[3])}
            for r in rows
        ]
    }
