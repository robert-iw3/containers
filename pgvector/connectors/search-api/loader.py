"""
Batch loader: JSONL file (or generated sample data) -> documents table.

  python loader.py --sample 500                 # load synthetic corpus
  python loader.py --file /data/docs.jsonl      # load {id,text,category} lines
"""

import argparse
import json
import os
import sys

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from corpus import embed, generate_corpus

HOST = os.environ.get("PGHOST", "pgvector")
DB = os.environ["POSTGRES_DB"]
RW_PASSWORD = os.environ["APP_RW_PASSWORD"]


def rows_from_file(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            yield (
                int(doc["id"]),
                doc["text"],
                doc.get("category", "general"),
                None,
                np.array(embed(doc["text"])),
            )


def rows_from_sample(n):
    for doc in generate_corpus(n):
        yield (
            doc["id"],
            doc["text"],
            doc["category"],
            doc["year"],
            np.array(doc["vector"]),
        )


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="JSONL file with id/text/category per line")
    src.add_argument("--sample", type=int, help="generate N synthetic docs")
    args = ap.parse_args()

    conn = psycopg.connect(
        host=HOST, port=5432, dbname=DB, user="app_rw", password=RW_PASSWORD,
        autocommit=True,
    )
    register_vector(conn)
    rows = list(rows_from_file(args.file) if args.file else rows_from_sample(args.sample))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO documents (id, text, category, year, embedding) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET "
            "text = EXCLUDED.text, category = EXCLUDED.category, "
            "year = EXCLUDED.year, embedding = EXCLUDED.embedding",
            rows,
        )
    conn.close()
    print(f"upserted {len(rows)} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
