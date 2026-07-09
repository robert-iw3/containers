# syntax=docker/dockerfile:1
# rustscan: The Modern Port Scanner. Find ports quickly (3 seconds at its fastest). Run scripts through our scripting engine (Python, Lua, Shell supported).
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS builder

RUN \
    # Install dependencies
    echo "Installing dependencies..." ; \
    apk add --no-cache \
    bash \
    ca-certificates \
    nmap \
    nmap-scripts \
    wget \
    bind-tools \
    libgcc \
    libstdc++ \
    openssl \
    openssl-dev \
    musl-dev \
    cargo \
    rust; \
    update-ca-certificates

COPY . .

RUN \
    # Install RustScan
    echo "Installing RustScan..." ; \
    cargo install rustscan

# packaged binary with runtime dependencies
FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL \
    org.opencontainers.image.name='rustscan' \
    org.opencontainers.image.description='The Modern Port Scanner.' \
    org.opencontainers.image.usage='https://github.com/bee-san/RustScan/wiki/Usage' \
    org.opencontainers.image.url='https://github.com/bee-san/RustScan' \
    org.opencontainers.image.vendor='bee-san' \
    org.opencontainers.image.licenses='GNU GENERAL PUBLIC LICENSE' \
    org.opencontainers.image.schema-version='2.4.1'

RUN \
    apk add --no-cache \
        bash \
        ca-certificates \
        nmap \
        nmap-scripts \
        wget \
        bind-tools \
        libgcc \
        libstdc++ \
        openssl; \
    update-ca-certificates

# Copy the RustScan binary from the builder stage
COPY --from=builder /root/.cargo/bin/rustscan /usr/local/bin/rustscan
CMD ["sh"]
