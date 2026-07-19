"""
LangChain retrieval over the Milvus stack.

Uses the deterministic hashing embedder so the demo runs offline; swap
HashingEmbeddings for any langchain embeddings class (OpenAIEmbeddings,
HuggingFaceEmbeddings, ...) to make this a production RAG retriever.
"""

import os

from langchain_core.embeddings import Embeddings
from langchain_milvus import Milvus

from corpus import embed, generate_corpus

MILVUS_URI = os.environ.get("MILVUS_URI", "http://milvus:19530")
MILVUS_TOKEN = "root:" + os.environ["MILVUS_ROOT_PASSWORD"]


class HashingEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [embed(t) for t in texts]

    def embed_query(self, text):
        return embed(text)


def main():
    docs = generate_corpus(100)
    store = Milvus(
        embedding_function=HashingEmbeddings(),
        collection_name="langchain_rag_demo",
        connection_args={"uri": MILVUS_URI, "token": MILVUS_TOKEN},
        auto_id=True,
        drop_old=True,
        consistency_level="Strong",
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
