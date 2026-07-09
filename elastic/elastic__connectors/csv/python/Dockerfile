# syntax=docker/dockerfile:1
# csv-connector: Sends CSV logs to Splunk and/or Elasticsearch

ARG repo="docker.io" \
    base_image="python:3.14-alpine" \
    image_hash="47f36929d95852c8aa959380eeeea761ba7411ebe793d090da4cd518ac3af237"

FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL org.opencontainers.image.name='CSV-Connector' \
    org.opencontainers.image.description='Connector for forwarding CSV logs to Splunk and Elasticsearch' \
    org.opencontainers.image.maintainer='RW'

RUN pip install --no-cache-dir requests elasticsearch_async aiohttp orjson watchdog pyyaml psutil python-magic

COPY csv_splunk_connector.py /app/csv_splunk_connector.py
COPY csv_elasticsearch_connector.py /app/csv_elasticsearch_connector.py
COPY schemas.yaml /app/schemas.yaml

WORKDIR /app

ENTRYPOINT ["/bin/sh", "-c", "if [ \"$ENABLE_SPLUNK\" = \"true\" ]; then python3 csv_splunk_connector.py; else python3 csv_elasticsearch_connector.py; fi"]