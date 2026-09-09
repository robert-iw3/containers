# syntax=docker/dockerfile:1
# Parquet connector: Parquet files to Splunk HEC or Elasticsearch.
#
# Build from the connectors root, not this directory, because the image needs
# core/ as well as this format's files:
#
#   podman build -f parquet/python/Dockerfile -t parquet-connector .
#
# docker-compose.yml already sets that context.

FROM docker.io/library/python:3.13-alpine

LABEL org.opencontainers.image.name='Parquet-Connector' \
      org.opencontainers.image.description='Forwards Parquet files to Splunk HEC or Elasticsearch' \
      org.opencontainers.image.maintainer='RW'

# Pinned: an unpinned install makes the image a different thing on every build.
RUN pip install --no-cache-dir \
        aiohttp==3.14.3 \
        pyyaml==6.0.3 \
        pyarrow==25.0.1

WORKDIR /app
COPY core/ /app/core/
COPY parquet/python/parquet_splunk_connector.py /app/
COPY parquet/python/parquet_elasticsearch_connector.py /app/
COPY parquet/python/schemas.yaml /app/schemas.yaml

# STATE_PATH is a FILE inside this directory. Mount a volume on the DIRECTORY,
# never on the file: a volume mounted at the file path creates a directory
# where the connector expects to write a file.
RUN mkdir -p /var/lib/connector /var/log/parquet_data
ENV STATE_PATH=/var/lib/connector/offsets.json \
    ENABLE_SPLUNK=true \
    PYTHONUNBUFFERED=1

RUN adduser -D -H -u 10001 connector \
    && chown -R connector /var/lib/connector /var/log/parquet_data
USER connector

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD pgrep -f "parquet_.*_connector.py" >/dev/null || exit 1

# ENABLE_SPLUNK picks the destination; both connectors share core/.
ENTRYPOINT ["/bin/sh", "-c", \
    "if [ \"$ENABLE_SPLUNK\" = \"true\" ]; then exec python3 /app/parquet_splunk_connector.py; else exec python3 /app/parquet_elasticsearch_connector.py; fi"]
