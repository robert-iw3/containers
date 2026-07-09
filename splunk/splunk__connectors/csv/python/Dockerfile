# syntax=docker/dockerfile:1
# csv-connector: Sends CSV logs to Splunk and/or Elasticsearch

ARG repo="docker.io" \
    base_image="python:3.9-alpine" \
    image_hash="f1a87fd82b7f2a2b9a7e6a07a5b3e99a1d0b8b6c7e4a0c4f7e8b2c1d9f3a5b6"

FROM ${repo}/${base_image}

LABEL org.opencontainers.image.name='CSV-Connector' \
    org.opencontainers.image.description='Connector for forwarding CSV logs to Splunk and Elasticsearch' \
    org.opencontainers.image.maintainer='RW'

RUN pip install --no-cache-dir requests elasticsearch_async aiohttp orjson watchdog pyyaml psutil python-magic

COPY csv_splunk_connector.py /app/csv_splunk_connector.py
COPY csv_elasticsearch_connector.py /app/csv_elasticsearch_connector.py
COPY schemas.yaml /app/schemas.yaml

WORKDIR /app

ENTRYPOINT ["/bin/sh", "-c", "if [ \"$ENABLE_SPLUNK\" = \"true\" ]; then python3 csv_splunk_connector.py; else python3 csv_elasticsearch_connector.py; fi"]