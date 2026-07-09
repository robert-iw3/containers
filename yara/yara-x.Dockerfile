# syntax=docker/dockerfile:1
FROM docker.io/debian:trixie

ENV PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TZ=UTC

RUN \
    apt-get update; \
    apt-get install -y \
        bash \
        curl \
        tzdata \
        git \
        ca-certificates \
        build-essential

RUN \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs > rustup.sh; \
    chmod +x rustup.sh && bash -c "./rustup.sh -y"; \
    rustup-init; \
    rustup update; \
    rustup install stable; \
    rustup toolchain install nightly --component rust-src; \
    git clone https://github.com/VirusTotal/yara-x; \
    cd yara-x; \
    cargo install --root /usr/local --path cli; \
    # smoke test
    yr help

CMD [ "bash" ]