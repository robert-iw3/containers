# Neo4j GraphRAG — OpenAI-compatible API + CLI loader.
FROM docker.io/python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/embedding_model \
    SENTENCE_TRANSFORMERS_HOME=/embedding_model

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# CPU-only torch (embeddings run on CPU here; the LLM's GPU path is Ollama's
# own container). Installing it first keeps sentence-transformers from pulling
# the multi-GB CUDA build from PyPI.
RUN pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY utils.py chains.py app.py loader.py ./

# Non-root; owns the embedding-model cache mount.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /embedding_model \
    && chown -R app:app /app /embedding_model
USER app

EXPOSE 8504

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=10 \
    CMD curl -fsS http://localhost:8504/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8504"]
