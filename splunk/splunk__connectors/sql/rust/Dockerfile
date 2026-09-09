# syntax=docker/dockerfile:1
# SQL connector, Rust build.
#
# Two stages so the runtime image carries the binary and not the compiler.
#
# NOTE: this crate is unbuilt and untested. Its sibling csv/rust fails to
# compile on a json! macro misuse; expect the same class here until proved
# otherwise with cargo build --release.

FROM docker.io/library/rust:1.90-alpine AS builder

WORKDIR /src
# reqwest pulls openssl-sys, whose build script needs the headers and
# pkgconfig; musl-dev alone fails at the build script.
RUN apk add --no-cache musl-dev openssl-dev pkgconfig
COPY Cargo.toml ./
COPY src/ ./src/
RUN cargo build --release

FROM docker.io/library/alpine:3.23

LABEL org.opencontainers.image.name='SQL-Connector' \
      org.opencontainers.image.description='Forwards database rows to Splunk and Elasticsearch' \
      org.opencontainers.image.maintainer='RW'

# ca-certificates is not optional: a TLS client with no trust store cannot
# verify any certificate, and the failure reads as a connection error.
RUN apk add --no-cache libgcc ca-certificates

WORKDIR /app
COPY --from=builder /src/target/release/sql-connector /app/sql-connector
COPY schemas.yaml /app/schemas.yaml

RUN adduser -D -H -u 10001 connector
USER connector

ENTRYPOINT ["/app/sql-connector"]
