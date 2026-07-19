# syntax=docker/dockerfile:1
# cribl: The Data Engine for IT and Security.
# Cribl ships glibc-linked binaries, so the base must be glibc (not alpine).
ARG repo="docker.io" \
    base_image="debian:trixie-slim" \
    cribl_version="4.18.2" \
    cribl_build="fd1f0d2f"

FROM ${repo}/${base_image}

ARG cribl_version cribl_build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        jq \
        tar \
        tini \
        uuid-runtime && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fLso - "https://cdn.cribl.io/dl/${cribl_version}/cribl-${cribl_version}-${cribl_build}-linux-x64.tgz" \
        | tar zx -C /opt && \
    chown -R root:root /opt/cribl && \
    chmod +x /opt/cribl/bin/cribl

WORKDIR /opt/cribl/bin
COPY --chmod=755 entrypoint.sh .
COPY --chmod=755 start-cribl.sh .
EXPOSE 9000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:9000/api/v1/health
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/cribl/bin/start-cribl.sh"]
