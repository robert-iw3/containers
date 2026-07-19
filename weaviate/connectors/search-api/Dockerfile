# Build context is the weaviate/ project root so the shared embedder
# (uat/corpus.py) is copied instead of duplicated.
FROM docker.io/library/python:3.12-slim

WORKDIR /app
COPY connectors/search-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY uat/corpus.py connectors/search-api/app.py connectors/search-api/loader.py ./

USER nobody
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
