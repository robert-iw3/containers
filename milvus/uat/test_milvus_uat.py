"""
UAT battery for the Milvus stack.

Phase 1 (default): auth, RBAC, collection lifecycle, ingest of the
synthetic corpus, index build, search recall, filtered search, upsert
and delete.

Phase 2 (-m verify, run by run-uat.sh after restarting the milvus
container): data survived the restart and search still works.
"""

import os

import pytest
from pymilvus import DataType, MilvusClient
from pymilvus.exceptions import MilvusException

from corpus import CATEGORIES, DIM, embed, generate_corpus

URI = os.environ.get("MILVUS_URI", "http://milvus:19530")
ROOT_TOKEN = "root:" + os.environ["MILVUS_ROOT_PASSWORD"]
COLLECTION = "uat_docs"
N_DOCS = 2000

READER_USER = "uat_reader"
READER_PASSWORD = "Uat-reader-pw1"
READER_ROLE = "uat_read_only"


@pytest.fixture(scope="session")
def client():
    c = MilvusClient(uri=URI, token=ROOT_TOKEN)
    yield c
    c.close()


@pytest.fixture(scope="session")
def corpus():
    return generate_corpus(N_DOCS)


# --------------------------------------------------------------- phase 1 --


def test_auth_rejects_bad_password():
    with pytest.raises(MilvusException):
        bad = MilvusClient(uri=URI, token="root:wrong-password")
        bad.list_collections()


def test_auth_rejects_factory_default():
    with pytest.raises(MilvusException):
        bad = MilvusClient(uri=URI, token="root:Milvus")
        bad.list_collections()


def test_auth_accepts_rotated_root(client):
    assert isinstance(client.list_collections(), list)


def test_create_collection(client):
    if COLLECTION in client.list_collections():
        client.drop_collection(COLLECTION)
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("text", DataType.VARCHAR, max_length=2048)
    schema.add_field("category", DataType.VARCHAR, max_length=64)
    schema.add_field("year", DataType.INT64)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=DIM)
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(
        COLLECTION,
        schema=schema,
        index_params=index_params,
        consistency_level="Strong",
    )
    assert COLLECTION in client.list_collections()


def test_ingest_corpus(client, corpus):
    batch = 500
    for i in range(0, len(corpus), batch):
        client.insert(COLLECTION, corpus[i : i + batch])
    client.flush(COLLECTION)
    client.load_collection(COLLECTION)
    res = client.query(COLLECTION, filter="id >= 0", output_fields=["count(*)"])
    assert res[0]["count(*)"] == N_DOCS


def test_search_recall_at_1(client, corpus):
    sample = corpus[:: len(corpus) // 50][:50]
    hits = 0
    for doc in sample:
        res = client.search(
            COLLECTION,
            data=[doc["vector"]],
            limit=1,
            search_params={"params": {"ef": 128}},
        )
        if res[0] and res[0][0]["id"] == doc["id"]:
            hits += 1
    recall = hits / len(sample)
    assert recall >= 0.95, f"recall@1 {recall}"


def test_semantic_query_lands_in_right_category(client):
    res = client.search(
        COLLECTION,
        data=[embed("carrier tracking shows the order stuck in the warehouse")],
        limit=5,
        output_fields=["category"],
    )
    top_categories = [hit["entity"]["category"] for hit in res[0]]
    assert top_categories.count("shipping") >= 3, top_categories


def test_filtered_search(client, corpus):
    doc = corpus[7]
    res = client.search(
        COLLECTION,
        data=[doc["vector"]],
        limit=10,
        filter='category == "returns"',
        output_fields=["category"],
    )
    assert len(res[0]) == 10
    assert all(hit["entity"]["category"] == "returns" for hit in res[0])


def test_scalar_range_filter(client):
    rows = client.query(
        COLLECTION, filter="year >= 2025", output_fields=["year"], limit=1000
    )
    assert rows and all(r["year"] >= 2025 for r in rows)


def test_upsert_and_delete(client, corpus):
    doc = dict(corpus[0])
    doc["text"] = "ticket doc00000 amended after escalation to tier two support"
    doc["vector"] = embed(doc["text"])
    client.upsert(COLLECTION, [doc])
    got = client.query(COLLECTION, filter="id == 0", output_fields=["text"])
    assert "amended" in got[0]["text"]

    client.delete(COLLECTION, filter="id == 1")
    assert client.query(COLLECTION, filter="id == 1") == []
    # restore for the persistence phase
    client.upsert(COLLECTION, [corpus[0], corpus[1]])
    client.flush(COLLECTION)


def test_rbac_read_only_role(client, corpus):
    if READER_USER in client.list_users():
        client.drop_user(READER_USER)
    if READER_ROLE in client.list_roles():
        for grant in client.describe_role(READER_ROLE)["privileges"]:
            client.revoke_privilege_v2(
                role_name=READER_ROLE,
                privilege=grant["privilege"],
                collection_name=grant["object_name"],
                db_name=grant.get("db_name", "default"),
            )
        client.drop_role(READER_ROLE)
    client.create_user(READER_USER, READER_PASSWORD)
    client.create_role(READER_ROLE)
    client.grant_privilege_v2(
        role_name=READER_ROLE,
        privilege="CollectionReadOnly",
        collection_name=COLLECTION,
        db_name="default",
    )
    client.grant_role(READER_USER, READER_ROLE)

    reader = MilvusClient(uri=URI, token=f"{READER_USER}:{READER_PASSWORD}")
    res = reader.search(COLLECTION, data=[corpus[3]["vector"]], limit=1)
    assert res[0][0]["id"] == corpus[3]["id"]
    with pytest.raises(Exception, match="(?i)permission deny"):
        reader.drop_collection(COLLECTION)
    reader.close()


# --------------------------------------------------------------- phase 2 --


@pytest.mark.verify
def test_data_survived_restart(client):
    client.load_collection(COLLECTION)
    res = client.query(COLLECTION, filter="id >= 0", output_fields=["count(*)"])
    assert res[0]["count(*)"] == N_DOCS


@pytest.mark.verify
def test_search_after_restart(client, corpus):
    doc = corpus[123]
    res = client.search(COLLECTION, data=[doc["vector"]], limit=1)
    assert res[0][0]["id"] == doc["id"]
