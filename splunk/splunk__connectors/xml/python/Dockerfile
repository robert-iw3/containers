# syntax=docker/dockerfile:1
# XML connector: tails XML files and posts them to Splunk HEC or Elasticsearch.
#
# Build from the connectors root, not this directory, because the image needs
# core/ as well as this format's files:
#
#   podman build -f xml/python/Dockerfile -t xml-connector .
#
# docker-compose.yml already sets that context.

FROM docker.io/library/python:3.13-alpine

LABEL org.opencontainers.image.name='XML-Connector' \
      org.opencontainers.image.description='Forwards XML files to Splunk HEC or Elasticsearch' \
      org.opencontainers.image.maintainer='RW'

# lxml needs libxml2 at run time and its headers to build.
RUN apk add --no-cache libxml2 libxslt

# Pinned: an unpinned install makes the image a different thing on every build.
RUN pip install --no-cache-dir \
        aiohttp==3.13.2 \
        pyyaml==6.0.3 \
        lxml==6.0.2

WORKDIR /app
COPY core/ /app/core/
COPY xml/python/xml_splunk_connector.py /app/
COPY xml/python/xml_elasticsearch_connector.py /app/
COPY xml/python/schemas.yaml /app/schemas.yaml

# Offsets live here. Mount a volume on it or a restart re-sends every file.
RUN mkdir -p /var/lib/connector /var/log/xml_data
ENV STATE_PATH=/var/lib/connector/offsets.json \
    ENABLE_SPLUNK=true \
    PYTHONUNBUFFERED=1

RUN adduser -D -H -u 10001 connector \
    && chown -R connector /var/lib/connector /var/log/xml_data
USER connector

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD pgrep -f "xml_.*_connector.py" >/dev/null || exit 1

# ENABLE_SPLUNK picks the destination; both connectors share core/.
ENTRYPOINT ["/bin/sh", "-c", \
    "if [ \"$ENABLE_SPLUNK\" = \"true\" ]; then exec python3 /app/xml_splunk_connector.py; else exec python3 /app/xml_elasticsearch_connector.py; fi"]
