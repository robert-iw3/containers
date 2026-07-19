"""
Semantic-search REST service backed by Weaviate.

Endpoints:
  GET  /healthz                     liveness + object count
  POST /documents [{id,text,category}]   embed + upsert
  POST /search {query, top_k, category}  vector search, optional filter

Embeddings come from corpus.embed (deterministic hashing embedder).
Swap embed() for a real model (e.g. sentence-transformers) in production;
everything else stays the same.
"""

import os
from contextlib import asynccontextmanager

import weaviate
from fastapi import FastAPI
from pydantic import BaseModel, Field
from weaviate.auth import AuthApiKey
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.util import generate_uuid5

from corpus import embed

HTTP_HOST = os.environ.get("WEAVIATE_HTTP_HOST", "weaviate")
GRPC_HOST = os.environ.get("WEAVIATE_GRPC_HOST", "weaviate")
ADMIN_KEY = os.environ["WEAVIATE_ADMIN_KEY"]
COLLECTION = os.environ.get("WEAVIATE_COLLECTION", "AppDocuments")

client = weaviate.connect_to_custom(
    http_host=HTTP_HOST, http_port=8080, http_secure=False,
    grpc_host=GRPC_HOST, grpc_port=50051, grpc_secure=False,
    auth_credentials=AuthApiKey(ADMIN_KEY),
)


@asynccontextmanager
async def lifespan(app):
    if not client.collections.exists(COLLECTION):
        client.collections.create(
            COLLECTION,
            properties=[
                Property(name="doc_id", data_type=DataType.INT),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="category", data_type=DataType.TEXT),
            ],
            vector_config=Configure.Vectors.self_provided(
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE,
                ),
            ),
        )
    yield
    client.close()


app = FastAPI(title="weaviate-semantic-search", lifespan=lifespan)


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
    col = client.collections.get(COLLECTION)
    total = col.aggregate.over_all(total_count=True).total_count
    return {"status": "ok", "collection": COLLECTION, "count": total}


@app.post("/documents")
def add_documents(docs: list[Document]):
    col = client.collections.get(COLLECTION)
    with col.batch.dynamic() as writer:
        for d in docs:
            writer.add_object(
                properties={"doc_id": d.id, "text": d.text, "category": d.category},
                vector=embed(d.text),
                uuid=generate_uuid5(d.id),
            )
    failed = len(col.batch.failed_objects)
    return {"upserted": len(docs) - failed, "failed": failed}


@app.post("/search")
def search(req: SearchRequest):
    col = client.collections.get(COLLECTION)
    kwargs = {}
    if req.category:
        kwargs["filters"] = Filter.by_property("category").equal(req.category)
    res = col.query.near_vector(
        near_vector=embed(req.query),
        limit=req.top_k,
        return_metadata=MetadataQuery(distance=True),
        **kwargs,
    )
    return {
        "hits": [
            {
                "id": o.properties["doc_id"],
                "score": 1.0 - o.metadata.distance,
                "text": o.properties["text"],
                "category": o.properties["category"],
            }
            for o in res.objects
        ]
    }
