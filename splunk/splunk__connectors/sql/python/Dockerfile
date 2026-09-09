# syntax=docker/dockerfile:1
# SQL connector: database tables to Splunk HEC or Elasticsearch.
#
# Build from the connectors root, not this directory, because the image needs
# core/ as well as this format's files:
#
#   podman build -f sql/python/Dockerfile -t sql-connector .
#
# docker-compose.yml already sets that context.

FROM docker.io/library/python:3.13-alpine

# The SQLite driver is in the standard library. Other drivers install per
# deployment via DB_EXTRA_PACKAGES; they are imported lazily, so a SQLite
# deployment does not need Oracle's client library present.
ARG DB_EXTRA_PACKAGES=""

LABEL org.opencontainers.image.name='SQL-Connector' \
      org.opencontainers.image.description='Forwards database tables to Splunk HEC or Elasticsearch' \
      org.opencontainers.image.maintainer='RW'

# Pinned: an unpinned install makes the image a different thing on every build.
RUN pip install --no-cache-dir \
        aiohttp==3.14.3 \
        pyyaml==6.0.3 \
        ${DB_EXTRA_PACKAGES}

WORKDIR /app
COPY core/ /app/core/
COPY sql/python/sql_splunk_connector.py /app/
COPY sql/python/sql_elasticsearch_connector.py /app/
COPY sql/python/schemas.yaml /app/schemas.yaml

# STATE_PATH is a FILE inside this directory. Mount a volume on the DIRECTORY,
# never on the file: a volume mounted at the file path creates a directory
# where the connector expects to write a file.
RUN mkdir -p /var/lib/connector /var/lib/connector
ENV STATE_PATH=/var/lib/connector/offsets.json \
    ENABLE_SPLUNK=true \
    PYTHONUNBUFFERED=1

RUN adduser -D -H -u 10001 connector \
    && chown -R connector /var/lib/connector /var/lib/connector
USER connector

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD pgrep -f "sql_.*_connector.py" >/dev/null || exit 1

# ENABLE_SPLUNK picks the destination; both connectors share core/.
ENTRYPOINT ["/bin/sh", "-c", \
    "if [ \"$ENABLE_SPLUNK\" = \"true\" ]; then exec python3 /app/sql_splunk_connector.py; else exec python3 /app/sql_elasticsearch_connector.py; fi"]
