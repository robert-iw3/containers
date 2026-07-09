# syntax=docker/dockerfile:1
# json-connector: Sends JSON logs to Splunk and/or Elasticsearch

ARG repo="docker.io" \
    base_image="python:3.14-alpine" \
    image_hash="47f36929d95852c8aa959380eeeea761ba7411ebe793d090da4cd518ac3af237"

FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL org.opencontainers.image.name='JSON-Connector' \
    org.opencontainers.image.description='Connector for forwarding JSON logs to Splunk and Elasticsearch' \
    org.opencontainers.image.maintainer='RW'

RUN pip install --no-cache-dir requests elasticsearch_async aiohttp orjson watchdog lxml pyyaml psutil

COPY json_splunk_connector.py /app/json_splunk_connector.py
COPY json_elasticsearch_connector.py /app/json_elasticsearch_connector.py
COPY schemas.yaml /app/schemas.yaml

WORKDIR /app

ENTRYPOINT ["/bin/sh", "-c", "if [ \"$ENABLE_SPLUNK\" = \"true\" ]; then python3 json_splunk_connector.py; else python3 json_elasticsearch_connector.py; fi"]