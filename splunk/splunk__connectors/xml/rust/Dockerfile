# syntax=docker/dockerfile:1
# xml-connector: Sends XML logs to Splunk and/or Elasticsearch

ARG repo="docker.io"
ARG base_image="rust:1.80-alpine"
ARG image_hash="f1a87fd82b7f2a2b9a7e6a07a5b3e99a1d0b8b6c7e4a0c4f7e8b2c1d9f3a5b6"

FROM ${repo}/${base_image}

LABEL org.opencontainers.image.name='XML-Connector' \
    org.opencontainers.image.description='Connector for forwarding XML logs to Splunk and Elasticsearch' \
    org.opencontainers.image.maintainer='RW'

RUN apk add --no-cache musl-dev
COPY . /app
WORKDIR /app
RUN cargo build --release
COPY schemas.yaml /app/schemas.yaml

ENTRYPOINT ["/app/target/release/xml-connector"]