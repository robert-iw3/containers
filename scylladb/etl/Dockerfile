FROM docker.io/python:3.13-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .

RUN useradd --system --uid 1000 etluser
USER etluser

CMD ["python", "worker.py"]
