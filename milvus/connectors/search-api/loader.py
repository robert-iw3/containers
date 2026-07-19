"""
Batch loader: JSONL file (or generated sample data) -> Milvus collection.

  python loader.py --sample 500                 # load synthetic corpus
  python loader.py --file /data/docs.jsonl      # load {id,text,category} lines
"""

import argparse
import json
import os
import sys

from pymilvus import MilvusClient

from corpus import embed, generate_corpus

MILVUS_URI = os.environ.get("MILVUS_URI", "http://milvus:19530")
MILVUS_TOKEN = "root:" + os.environ["MILVUS_ROOT_PASSWORD"]
COLLECTION = os.environ.get("MILVUS_COLLECTION", "app_documents")


def rows_from_file(path):
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


def rows_from_sample(n):
    for doc in generate_corpus(n):
        yield {k: doc[k] for k in ("id", "text", "category", "vector")}


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="JSONL file with id/text/category per line")
    src.add_argument("--sample", type=int, help="generate N synthetic docs")
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()

    client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
    if COLLECTION not in client.list_collections():
        print(
            f"collection {COLLECTION!r} missing — start the search-api once to create it",
            file=sys.stderr,
        )
        return 1

    rows = list(rows_from_file(args.file) if args.file else rows_from_sample(args.sample))
    total = 0
    for i in range(0, len(rows), args.batch):
        res = client.upsert(COLLECTION, rows[i : i + args.batch])
        total += res["upsert_count"]
    client.flush(COLLECTION)
    print(f"upserted {total} documents into {COLLECTION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
