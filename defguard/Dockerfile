FROM node:24-alpine AS web
WORKDIR /app
COPY web/package.json web/pnpm-lock.yaml web/.npmrc .
RUN npm i -g pnpm && pnpm install --frozen-lockfile --prod
COPY web/ .
RUN pnpm run generate-translation-types && pnpm build && rm -rf node_modules

FROM rust:1.96.1-slim-bookworm AS chef
WORKDIR /build
RUN cargo install cargo-chef && rustup component add rustfmt
RUN apt-get update && apt-get install -y protobuf-compiler libprotobuf-dev && rm -rf /var/lib/apt/lists/*

FROM chef AS planner
COPY Cargo.toml Cargo.lock ./
COPY src src
COPY model-derive model-derive
COPY proto proto
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /build/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json
COPY --from=web /app/dist ./web/dist
COPY web/src/shared/images/svg ./web/src/shared/images/svg
COPY user_agent_header_regexes.yaml /build/user_agent_header_regexes.yaml
COPY Cargo.toml Cargo.lock build.rs ./
COPY .git .git
COPY .sqlx .sqlx
COPY src src
COPY templates templates
COPY model-derive model-derive
COPY proto proto
COPY migrations migrations
RUN cargo build --release && cargo install --locked --path . --root /build

FROM gcr.io/distroless/cc-debian12
WORKDIR /app
COPY --from=builder /build/bin/defguard .
COPY --from=builder /build/web ./web
COPY --from=builder /build/templates ./templates
COPY --from=builder /build/user_agent_header_regexes.yaml .
USER nonroot
EXPOSE 8000 50055
ENTRYPOINT ["./defguard"]