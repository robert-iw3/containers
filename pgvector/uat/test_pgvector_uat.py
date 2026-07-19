"""
UAT battery for the pgvector stack.

Phase 1 (default): auth (admin, app roles, bad password), schema and
extension, ingest of the synthetic corpus, HNSW cosine search recall,
filtered search, update/delete, and role separation.

Phase 2 (-m verify, run by run-uat.sh after restarting the postgres
container): data survived the restart and search still works.
"""

import os

import numpy as np
import psycopg
import pytest
from pgvector.psycopg import register_vector

from corpus import embed, generate_corpus

HOST = os.environ.get("PGHOST", "pgvector")
DB = os.environ["POSTGRES_DB"]
ADMIN_USER = os.environ["POSTGRES_USER"]
ADMIN_PASSWORD = os.environ["POSTGRES_PASSWORD"]
RW_PASSWORD = os.environ["APP_RW_PASSWORD"]
RO_PASSWORD = os.environ["APP_RO_PASSWORD"]
N_DOCS = 2000


def connect(user, password):
    conn = psycopg.connect(
        host=HOST, port=5432, dbname=DB, user=user, password=password, autocommit=True
    )
    register_vector(conn)
    return conn


@pytest.fixture(scope="session")
def admin():
    conn = connect(ADMIN_USER, ADMIN_PASSWORD)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def rw():
    conn = connect("app_rw", RW_PASSWORD)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def corpus():
    return generate_corpus(N_DOCS)


# --------------------------------------------------------------- phase 1 --


def test_auth_rejects_bad_password():
    with pytest.raises(psycopg.OperationalError):
        connect(ADMIN_USER, "wrong-password")


def test_extension_and_schema(admin):
    ver = admin.execute(
        "SELECT extversion FROM pg_extension WHERE extname='vector'"
    ).fetchone()
    assert ver and ver[0].startswith("0.8")
    idx = admin.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname='documents_embedding_idx'"
    ).fetchone()
    assert idx and "hnsw" in idx[0]


def test_ingest_corpus(rw, corpus):
    rw.execute("DELETE FROM documents")
    with rw.cursor().copy(
        "COPY documents (id, text, category, year, embedding) FROM STDIN WITH (FORMAT BINARY)"
    ) as copy:
        copy.set_types(["int8", "text", "text", "int4", "vector"])
        for doc in corpus:
            copy.write_row(
                (
                    doc["id"],
                    doc["text"],
                    doc["category"],
                    doc["year"],
                    np.array(doc["vector"]),
                )
            )
    count = rw.execute("SELECT count(*) FROM documents").fetchone()[0]
    assert count == N_DOCS


def test_search_recall_at_1(rw, corpus):
    sample = corpus[:: len(corpus) // 50][:50]
    hits = 0
    for doc in sample:
        row = rw.execute(
            "SELECT id FROM documents ORDER BY embedding <=> %s LIMIT 1",
            (np.array(doc["vector"]),),
        ).fetchone()
        if row and row[0] == doc["id"]:
            hits += 1
    recall = hits / len(sample)
    assert recall >= 0.95, f"recall@1 {recall}"


def test_query_uses_hnsw_index(rw, corpus):
    with rw.transaction():
        rw.execute("SET LOCAL enable_seqscan = off")
        plan = "\n".join(
            r[0]
            for r in rw.execute(
                "EXPLAIN SELECT id FROM documents ORDER BY embedding <=> %s LIMIT 5",
                (np.array(corpus[0]["vector"]),),
            ).fetchall()
        )
    assert "documents_embedding_idx" in plan, plan


def test_semantic_query_lands_in_right_category(rw):
    rows = rw.execute(
        "SELECT category FROM documents ORDER BY embedding <=> %s LIMIT 5",
        (np.array(embed("carrier tracking shows the order stuck in the warehouse")),),
    ).fetchall()
    top_categories = [r[0] for r in rows]
    assert top_categories.count("shipping") >= 3, top_categories


def test_filtered_search(rw, corpus):
    rows = rw.execute(
        "SELECT category FROM documents WHERE category = 'returns' "
        "ORDER BY embedding <=> %s LIMIT 10",
        (np.array(corpus[7]["vector"]),),
    ).fetchall()
    assert len(rows) == 10
    assert all(r[0] == "returns" for r in rows)


def test_scalar_range_filter(rw):
    rows = rw.execute("SELECT year FROM documents WHERE year >= 2025").fetchall()
    assert rows and all(r[0] >= 2025 for r in rows)


def test_update_and_delete(rw, corpus):
    amended = "ticket doc00000 amended after escalation to tier two support"
    rw.execute(
        "UPDATE documents SET text = %s, embedding = %s WHERE id = 0",
        (amended, np.array(embed(amended))),
    )
    got = rw.execute("SELECT text FROM documents WHERE id = 0").fetchone()[0]
    assert "amended" in got

    rw.execute("DELETE FROM documents WHERE id = 1")
    assert rw.execute("SELECT 1 FROM documents WHERE id = 1").fetchone() is None

    # restore both docs for the persistence phase
    rw.execute(
        "UPDATE documents SET text = %s, embedding = %s WHERE id = 0",
        (corpus[0]["text"], np.array(corpus[0]["vector"])),
    )
    rw.execute(
        "INSERT INTO documents (id, text, category, year, embedding) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            corpus[1]["id"],
            corpus[1]["text"],
            corpus[1]["category"],
            corpus[1]["year"],
            np.array(corpus[1]["vector"]),
        ),
    )


def test_readonly_role_can_query_but_not_write(corpus):
    ro = connect("app_ro", RO_PASSWORD)
    try:
        row = ro.execute(
            "SELECT id FROM documents ORDER BY embedding <=> %s LIMIT 1",
            (np.array(corpus[3]["vector"]),),
        ).fetchone()
        assert row[0] == corpus[3]["id"]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            ro.execute("DELETE FROM documents WHERE id = 0")
    finally:
        ro.close()


# --------------------------------------------------------------- phase 2 --


@pytest.mark.verify
def test_data_survived_restart(rw):
    assert rw.execute("SELECT count(*) FROM documents").fetchone()[0] == N_DOCS


@pytest.mark.verify
def test_search_after_restart(rw, corpus):
    row = rw.execute(
        "SELECT id FROM documents ORDER BY embedding <=> %s LIMIT 1",
        (np.array(corpus[123]["vector"]),),
    ).fetchone()
    assert row[0] == corpus[123]["id"]
