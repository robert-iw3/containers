"""
LangChain retrieval over the Weaviate stack.

Uses the deterministic hashing embedder so the demo runs offline; swap
HashingEmbeddings for any langchain embeddings class (OpenAIEmbeddings,
HuggingFaceEmbeddings, ...) to make this a production RAG retriever.
"""

import os

import weaviate
from langchain_core.embeddings import Embeddings
from langchain_weaviate.vectorstores import WeaviateVectorStore
from weaviate.auth import AuthApiKey

from corpus import embed, generate_corpus

HTTP_HOST = os.environ.get("WEAVIATE_HTTP_HOST", "weaviate")
GRPC_HOST = os.environ.get("WEAVIATE_GRPC_HOST", "weaviate")
ADMIN_KEY = os.environ["WEAVIATE_ADMIN_KEY"]


class HashingEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [embed(t) for t in texts]

    def embed_query(self, text):
        return embed(text)


def main():
    docs = generate_corpus(100)
    client = weaviate.connect_to_custom(
        http_host=HTTP_HOST, http_port=8080, http_secure=False,
        grpc_host=GRPC_HOST, grpc_port=50051, grpc_secure=False,
        auth_credentials=AuthApiKey(ADMIN_KEY),
    )
    try:
        if client.collections.exists("LangchainRagDemo"):
            client.collections.delete("LangchainRagDemo")
        store = WeaviateVectorStore(
            client=client,
            index_name="LangchainRagDemo",
            text_key="text",
            embedding=HashingEmbeddings(),
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
    finally:
        client.close()


if __name__ == "__main__":
    main()
