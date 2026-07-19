"""
LangChain retrieval over the pgvector stack (langchain-postgres).

Uses the deterministic hashing embedder so the demo runs offline; swap
HashingEmbeddings for any langchain embeddings class (OpenAIEmbeddings,
HuggingFaceEmbeddings, ...) to make this a production RAG retriever.
langchain-postgres manages its own tables, so it connects as the admin
role rather than app_rw.
"""

import os

from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from corpus import embed, generate_corpus

HOST = os.environ.get("PGHOST", "pgvector")
DB = os.environ["POSTGRES_DB"]
ADMIN_USER = os.environ["POSTGRES_USER"]
ADMIN_PASSWORD = os.environ["POSTGRES_PASSWORD"]


class HashingEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [embed(t) for t in texts]

    def embed_query(self, text):
        return embed(text)


def main():
    docs = generate_corpus(100)
    store = PGVector(
        embeddings=HashingEmbeddings(),
        collection_name="langchain_rag_demo",
        connection=f"postgresql+psycopg://{ADMIN_USER}:{ADMIN_PASSWORD}@{HOST}:5432/{DB}",
        pre_delete_collection=True,
    )
    store.add_texts(
        texts=[d["text"] for d in docs],
        metadatas=[{"category": d["category"]} for d in docs],
    )

    retriever = store.as_retriever(search_kwargs={"k": 3})
    query = "the carrier tracking shows my order is stuck"
    results = retriever.invoke(query)

    print(f"query: {query}")
    for i, doc in enumerate(results, 1):
        print(f"  {i}. [{doc.metadata['category']}] {doc.page_content[:80]}")
    assert results, "retriever returned nothing"
    assert results[0].metadata["category"] == "shipping", results[0].metadata
    print("retrieval OK — top hit is a shipping document")


if __name__ == "__main__":
    main()
