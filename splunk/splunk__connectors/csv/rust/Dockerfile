# syntax=docker/dockerfile:1
FROM docker.io/rust:1.80-alpine AS builder
WORKDIR /usr/src/csv-connector
COPY . .
RUN apk add --no-cache musl-dev
RUN cargo build --release

FROM docker.io/alpine:3.23
LABEL org.opencontainers.image.name='CSV-Connector' \
      org.opencontainers.image.description='Connector for forwarding CSV logs to Splunk and Elasticsearch' \
      org.opencontainers.image.maintainer='RW'
RUN apk add --no-cache libgcc
COPY --from=builder /usr/src/csv-connector/target/release/csv-connector /app/csv-connector
COPY schemas.yaml /app/schemas.yaml
WORKDIR /app
ENTRYPOINT ["/app/csv-connector"]