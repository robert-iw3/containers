# syntax=docker/dockerfile:1
# xml-connector: Sends XML logs to Splunk and/or Elasticsearch

ARG repo="docker.io"
ARG base_image="rust:1.96.1-alpine3.22"
ARG image_hash="8b5aee3b8fb41756d8447a47f96edc87a21f1e0c2b5ad2f3059542637d6c9b93"

FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL org.opencontainers.image.name='XML-Connector' \
    org.opencontainers.image.description='Connector for forwarding XML logs to Splunk and Elasticsearch' \
    org.opencontainers.image.maintainer='RW'

RUN apk add --no-cache musl-dev
COPY . /app
WORKDIR /app
RUN cargo build --release
COPY schemas.yaml /app/schemas.yaml

ENTRYPOINT ["/app/target/release/xml-connector"]