# syntax=docker/dockerfile:1
# Parquet connector, Rust build.
#
# NOTE: this crate is unbuilt and untested. Its sibling csv/rust fails to
# compile on a json! macro misuse; expect the same class here until proved
# otherwise with cargo build --release.

FROM docker.io/library/rust:1.90-slim AS builder

WORKDIR /src
# reqwest pulls openssl-sys, whose build script needs the headers and
# pkg-config; without them the build fails before any of this crate compiles.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml ./
COPY src/ ./src/
RUN cargo build --release

FROM docker.io/library/debian:trixie-slim

LABEL org.opencontainers.image.name='Parquet-Connector' \
      org.opencontainers.image.description='Forwards Parquet files to Splunk and Elasticsearch' \
      org.opencontainers.image.maintainer='RW'

# libssl3 is the runtime library; libssl-dev is the build-time headers and
# belongs in the builder, not here. ca-certificates is not optional: a TLS
# client with no trust store cannot verify any certificate.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libssl3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /src/target/release/parquet-connector /app/parquet-connector
COPY schemas.yaml /app/schemas.yaml

RUN useradd -r -u 10001 connector && mkdir -p /app/data && chown connector /app/data
USER connector

# Prometheus metrics, served by src/main.py's start_http_server.
EXPOSE 9000

ENTRYPOINT ["/app/parquet-connector"]
