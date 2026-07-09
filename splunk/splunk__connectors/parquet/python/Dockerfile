# syntax=docker/dockerfile:1
FROM python:3.12-slim
LABEL org.opencontainers.image.name='Parquet-Connector' \
      org.opencontainers.image.description='Python connector for processing Parquet files and forwarding to Splunk' \
      org.opencontainers.image.maintainer='RW'
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY schemas.yaml .
RUN mkdir -p /app/data
EXPOSE 9000
ENTRYPOINT ["python3", "src/main.py"]