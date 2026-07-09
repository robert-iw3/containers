# syntax=docker/dockerfile:1
FROM rust:1.82-slim AS builder
WORKDIR /app
COPY Cargo.toml .
COPY src/ ./src/
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/parquet-connector .
COPY schemas.yaml .
RUN mkdir -p /app/data
EXPOSE 9000
ENTRYPOINT ["./parquet-connector"]