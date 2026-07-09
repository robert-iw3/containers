# syntax=docker/dockerfile:1
# nuclei: Fast and customizable vulnerability scanner based on simple YAML based DSL.
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS go-builder

ENV GOPATH=/usr/local/bin/go \
    VER=3.11.0

RUN \
    apk add --no-cache -t .nuclei-deps \
        build-base \
        ca-certificates \
        go \
        git; \
    apk add --no-cache -t .av-scan \
        clamav \
        freshclam; \
    mkdir -p ${GOPATH}/src/github.com/nuclei; \
    cd ${GOPATH}/src/github.com/nuclei; \
    git clone --depth 1 --branch v${VER} https://github.com/projectdiscovery/nuclei; \
    cd nuclei/; \
    cd cmd/nuclei/; \
    export GO111MODULE=on; \
    go install; \
    apk del --no-network --purge .nuclei-deps; \
    freshclam; \
    clamscan -rvi -l /build_clamav_scan.log --exclude-dir="^/sys|^/dev" /; \
    grep -Hrn FOUND /build_clamav_scan.log; \
    apk del --no-network --purge .av-scan; \
    rm -rf /var/cache/apk/*; \
    rm -rf ${GOPATH}/src/

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN \
    addgroup -g 65535 nuclei; \
    adduser --shell /sbin/nologin --disabled-password -h /home/nuclei --uid 65535 --ingroup nuclei nuclei; \
    apk add --no-cache \
        bash \
        bind-tools \
        ca-certificates \
        chromium

COPY --chown=nuclei:nuclei --from=go-builder /usr/local/bin/go/bin/nuclei /usr/local/bin/
COPY --chown=nuclei:nuclei --from=go-builder /build_clamav_scan.log /home/nuclei
COPY --chown=nuclei:nuclei ./custom-templates /home/nuclei/

WORKDIR /home/nuclei
USER nuclei
CMD [ "bash" ]
LABEL \
    org.opencontainers.image.name='Nuclei' \
    org.opencontainers.image.description='Fast and extensible vulnerability scanner.' \
    org.opencontainers.image.licenses='MIT' \
    org.opencontainers.image.schema-version='3.11.0'