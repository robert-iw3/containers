# syntax=docker/dockerfile:1
FROM docker.io/rust:1.80-alpine AS builder
WORKDIR /usr/src/sql-connector
COPY . .
RUN apk add --no-cache musl-dev
RUN cargo build --release

FROM docker.io/alpine:3.23
LABEL org.opencontainers.image.name='SQL-Connector' \
      org.opencontainers.image.description='Connector for querying SQL databases and forwarding to Splunk' \
      org.opencontainers.image.maintainer='RW'
RUN apk add --no-cache libgcc
COPY --from=builder /usr/src/sql-connector/target/release/sql-connector /app/sql-connector
COPY schemas.yaml /app/schemas.yaml
WORKDIR /app
EXPOSE 9000
ENTRYPOINT ["/app/sql-connector"]