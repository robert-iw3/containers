"""
UAT battery for the Weaviate stack.

Phase 1 (default): auth (admin, read-only, anonymous, bad key),
collection lifecycle, ingest of the synthetic corpus with self-provided
vectors, HNSW search recall, filtered search, update and delete.

Phase 2 (-m verify, run by run-uat.sh after restarting the weaviate
container): data survived the restart and search still works.
"""

import os

import pytest
import weaviate
from weaviate.auth import AuthApiKey
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.query import Filter
from weaviate.util import generate_uuid5

from corpus import embed, generate_corpus

HTTP_HOST = os.environ.get("WEAVIATE_HTTP_HOST", "weaviate")
GRPC_HOST = os.environ.get("WEAVIATE_GRPC_HOST", "weaviate")
ADMIN_KEY = os.environ["WEAVIATE_ADMIN_KEY"]
READONLY_KEY = os.environ["WEAVIATE_READONLY_KEY"]
COLLECTION = "UatDocs"
N_DOCS = 2000


def connect(key):
    return weaviate.connect_to_custom(
        http_host=HTTP_HOST, http_port=8080, http_secure=False,
        grpc_host=GRPC_HOST, grpc_port=50051, grpc_secure=False,
        auth_credentials=AuthApiKey(key),
    )


def properties_of(doc):
    return {
        "doc_id": doc["id"],
        "text": doc["text"],
        "category": doc["category"],
        "year": doc["year"],
    }


@pytest.fixture(scope="session")
def client():
    c = connect(ADMIN_KEY)
    yield c
    c.close()


@pytest.fixture(scope="session")
def corpus():
    return generate_corpus(N_DOCS)


# --------------------------------------------------------------- phase 1 --


def test_auth_rejects_anonymous():
    with pytest.raises(Exception, match="(?i)401|auth|anon"):
        c = weaviate.connect_to_custom(
            http_host=HTTP_HOST, http_port=8080, http_secure=False,
            grpc_host=GRPC_HOST, grpc_port=50051, grpc_secure=False,
        )
        c.collections.list_all()


def test_auth_rejects_bad_key():
    with pytest.raises(Exception, match="(?i)401|auth"):
        c = connect("not-a-real-key")
        c.collections.list_all()


def test_auth_accepts_admin_key(client):
    assert client.is_ready()


def test_create_collection(client):
    if client.collections.exists(COLLECTION):
        client.collections.delete(COLLECTION)
    client.collections.create(
        COLLECTION,
        properties=[
            Property(name="doc_id", data_type=DataType.INT),
            Property(name="text", data_type=DataType.TEXT),
            Property(name="category", data_type=DataType.TEXT),
            Property(name="year", data_type=DataType.INT),
        ],
        vector_config=Configure.Vectors.self_provided(
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
            ),
        ),
    )
    assert client.collections.exists(COLLECTION)


def test_ingest_corpus(client, corpus):
    col = client.collections.get(COLLECTION)
    with col.batch.dynamic() as writer:
        for doc in corpus:
            writer.add_object(
                properties=properties_of(doc),
                vector=doc["vector"],
                uuid=generate_uuid5(doc["id"]),
            )
    assert not col.batch.failed_objects, col.batch.failed_objects[:3]
    total = col.aggregate.over_all(total_count=True).total_count
    assert total == N_DOCS


def test_search_recall_at_1(client, corpus):
    col = client.collections.get(COLLECTION)
    sample = corpus[:: len(corpus) // 50][:50]
    hits = 0
    for doc in sample:
        res = col.query.near_vector(near_vector=doc["vector"], limit=1)
        if res.objects and res.objects[0].properties["doc_id"] == doc["id"]:
            hits += 1
    recall = hits / len(sample)
    assert recall >= 0.95, f"recall@1 {recall}"


def test_semantic_query_lands_in_right_category(client):
    col = client.collections.get(COLLECTION)
    res = col.query.near_vector(
        near_vector=embed("carrier tracking shows the order stuck in the warehouse"),
        limit=5,
    )
    top_categories = [o.properties["category"] for o in res.objects]
    assert top_categories.count("shipping") >= 3, top_categories


def test_filtered_search(client, corpus):
    col = client.collections.get(COLLECTION)
    res = col.query.near_vector(
        near_vector=corpus[7]["vector"],
        limit=10,
        filters=Filter.by_property("category").equal("returns"),
    )
    assert len(res.objects) == 10
    assert all(o.properties["category"] == "returns" for o in res.objects)


def test_scalar_range_filter(client):
    col = client.collections.get(COLLECTION)
    res = col.query.fetch_objects(
        filters=Filter.by_property("year").greater_or_equal(2025), limit=1000
    )
    assert res.objects and all(o.properties["year"] >= 2025 for o in res.objects)


def test_update_and_delete(client, corpus):
    col = client.collections.get(COLLECTION)
    uid0 = generate_uuid5(corpus[0]["id"])
    amended = "ticket doc00000 amended after escalation to tier two support"
    col.data.update(uuid=uid0, properties={"text": amended}, vector=embed(amended))
    assert "amended" in col.query.fetch_object_by_id(uid0).properties["text"]

    uid1 = generate_uuid5(corpus[1]["id"])
    col.data.delete_by_id(uid1)
    assert col.query.fetch_object_by_id(uid1) is None

    # restore both docs for the persistence phase
    col.data.update(
        uuid=uid0, properties=properties_of(corpus[0]), vector=corpus[0]["vector"]
    )
    col.data.insert(
        properties=properties_of(corpus[1]),
        vector=corpus[1]["vector"],
        uuid=uid1,
    )


def test_readonly_key_can_query_but_not_write(client, corpus):
    reader = connect(READONLY_KEY)
    try:
        col = reader.collections.get(COLLECTION)
        res = col.query.near_vector(near_vector=corpus[3]["vector"], limit=1)
        assert res.objects[0].properties["doc_id"] == corpus[3]["id"]
        with pytest.raises(Exception, match="(?i)403|forbidden"):
            reader.collections.create("UatDenied")
    finally:
        reader.close()


# --------------------------------------------------------------- phase 2 --


@pytest.mark.verify
def test_data_survived_restart(client):
    col = client.collections.get(COLLECTION)
    assert col.aggregate.over_all(total_count=True).total_count == N_DOCS


@pytest.mark.verify
def test_search_after_restart(client, corpus):
    col = client.collections.get(COLLECTION)
    res = col.query.near_vector(near_vector=corpus[123]["vector"], limit=1)
    assert res.objects[0].properties["doc_id"] == corpus[123]["id"]
