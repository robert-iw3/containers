# Build context is the milvus/ project root (shared embedder in uat/corpus.py).
FROM docker.io/library/python:3.12-slim

WORKDIR /app
COPY connectors/langchain-rag/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY uat/corpus.py connectors/langchain-rag/rag_example.py ./

USER nobody
CMD ["python", "rag_example.py"]
