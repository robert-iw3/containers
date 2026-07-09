# syntax=docker/dockerfile:1
# cribl: The Data Engine for IT and Security.
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN \
    apk update ; \
    apk add --no-cache \
        bash \
        curl \
        tar \
        jq \
        ca-certificates \
        git \
        openssh-client \
        iproute2 \
        libstdc++ \
        libcap-utils \
        uuidgen \
        tini \
        bash \
        python3 \
        py3-pip; \
    apk cache clean; \
    rm -rf /var/cache/apk/*; \
    curl -Lso - $(curl https://cdn.cribl.io/dl/latest-x64) | tar zxv -C /opt; \
    chown -R root:root /opt/cribl; \
    chmod +x /opt/cribl/bin/cribl; \
    chmod -R +x /opt/cribl/bin/*.sh

WORKDIR /opt/cribl/bin
COPY --chmod=755 entrypoint.sh .
COPY --chmod=755 start-cribl.sh .
EXPOSE 9000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:9000/api/v1/health
ENTRYPOINT ["/sbin/tini", "--", "/opt/cribl/bin/start-cribl.sh"]