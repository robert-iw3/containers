# syntax=docker/dockerfile:1
FROM python:3.12-slim
LABEL org.opencontainers.image.name='SQL-Connector' \
      org.opencontainers.image.description='Python connector for querying SQL databases and forwarding to Splunk' \
      org.opencontainers.image.maintainer='RW'
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY schemas.yaml .
EXPOSE 9000
ENTRYPOINT ["python3", "src/main.py"]