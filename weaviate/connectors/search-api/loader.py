"""
Batch loader: JSONL file (or generated sample data) -> Weaviate collection.

  python loader.py --sample 500                 # load synthetic corpus
  python loader.py --file /data/docs.jsonl      # load {id,text,category} lines
"""

import argparse
import json
import os
import sys

import weaviate
from weaviate.auth import AuthApiKey
from weaviate.util import generate_uuid5

from corpus import embed, generate_corpus

HTTP_HOST = os.environ.get("WEAVIATE_HTTP_HOST", "weaviate")
GRPC_HOST = os.environ.get("WEAVIATE_GRPC_HOST", "weaviate")
ADMIN_KEY = os.environ["WEAVIATE_ADMIN_KEY"]
COLLECTION = os.environ.get("WEAVIATE_COLLECTION", "AppDocuments")


def docs_from_file(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            yield {
                "id": int(doc["id"]),
                "text": doc["text"],
                "category": doc.get("category", "general"),
                "vector": embed(doc["text"]),
            }


def docs_from_sample(n):
    for doc in generate_corpus(n):
        yield {k: doc[k] for k in ("id", "text", "category", "vector")}


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="JSONL file with id/text/category per line")
    src.add_argument("--sample", type=int, help="generate N synthetic docs")
    args = ap.parse_args()

    client = weaviate.connect_to_custom(
        http_host=HTTP_HOST, http_port=8080, http_secure=False,
        grpc_host=GRPC_HOST, grpc_port=50051, grpc_secure=False,
        auth_credentials=AuthApiKey(ADMIN_KEY),
    )
    try:
        if not client.collections.exists(COLLECTION):
            print(
                f"collection {COLLECTION!r} missing — start the search-api once to create it",
                file=sys.stderr,
            )
            return 1
        col = client.collections.get(COLLECTION)
        docs = docs_from_file(args.file) if args.file else docs_from_sample(args.sample)
        total = 0
        with col.batch.dynamic() as writer:
            for doc in docs:
                writer.add_object(
                    properties={
                        "doc_id": doc["id"],
                        "text": doc["text"],
                        "category": doc["category"],
                    },
                    vector=doc["vector"],
                    uuid=generate_uuid5(doc["id"]),
                )
                total += 1
        failed = len(col.batch.failed_objects)
        print(f"upserted {total - failed} documents into {COLLECTION} ({failed} failed)")
        return 1 if failed else 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
