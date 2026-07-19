"""
Semantic-search REST service backed by Milvus.

Endpoints:
  GET  /healthz                     liveness + collection stats
  POST /documents [{id,text,category}]   embed + upsert
  POST /search {query, top_k, category}  vector search, optional filter

Embeddings come from corpus.embed (deterministic hashing embedder).
Swap embed() for a real model (e.g. sentence-transformers) in production;
everything else stays the same.
"""

import os

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pymilvus import DataType, MilvusClient

from corpus import DIM, embed

MILVUS_URI = os.environ.get("MILVUS_URI", "http://milvus:19530")
MILVUS_TOKEN = "root:" + os.environ["MILVUS_ROOT_PASSWORD"]
COLLECTION = os.environ.get("MILVUS_COLLECTION", "app_documents")

app = FastAPI(title="milvus-semantic-search")
client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)


class Document(BaseModel):
    id: int
    text: str
    category: str = "general"


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    category: str | None = None


@app.on_event("startup")
def ensure_collection():
    if COLLECTION in client.list_collections():
        return
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("text", DataType.VARCHAR, max_length=4096)
    schema.add_field("category", DataType.VARCHAR, max_length=64)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=DIM)
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(
        COLLECTION, schema=schema, index_params=index_params,
        consistency_level="Strong",
    )


@app.get("/healthz")
def healthz():
    stats = client.get_collection_stats(COLLECTION)
    return {"status": "ok", "collection": COLLECTION, "stats": stats}


@app.post("/documents")
def add_documents(docs: list[Document]):
    rows = [
        {"id": d.id, "text": d.text, "category": d.category, "vector": embed(d.text)}
        for d in docs
    ]
    res = client.upsert(COLLECTION, rows)
    return {"upserted": res["upsert_count"]}


@app.post("/search")
def search(req: SearchRequest):
    kwargs = {}
    if req.category:
        kwargs["filter"] = f'category == "{req.category}"'
    res = client.search(
        COLLECTION,
        data=[embed(req.query)],
        limit=req.top_k,
        output_fields=["text", "category"],
        **kwargs,
    )
    return {
        "hits": [
            {
                "id": hit["id"],
                "score": hit["distance"],
                "text": hit["entity"]["text"],
                "category": hit["entity"]["category"],
            }
            for hit in res[0]
        ]
    }
