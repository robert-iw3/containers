# syntax=docker/dockerfile:1
# trivy: is a comprehensive and versatile security scanner.
ARG repo="docker.io" \
    base_image="alpine:latest" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS build-env

ENV GOPATH=/usr/local/bin/go \
    VER=0.72.0

RUN \
    apk add --no-cache -t .trivy-deps ca-certificates go git wget; \
    mkdir -p ${GOPATH}/src/github.com/aquasecurity; \
    cd ${GOPATH}/src/github.com/aquasecurity; \
    git clone --depth 1 --branch v${VER} https://github.com/aquasecurity/trivy; \
    cd trivy/; \
    cd cmd/trivy/; \
    export GO111MODULE=on; \
    go install; \
    mkdir /contrib; cd /contrib; \
    wget https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/html.tpl; \
    wget https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/junit.tpl; \
    wget https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/gitlab-codequality.tpl; \
    wget https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/gitlab.tpl; \
    apk del --purge .trivy-deps; \
    rm -rf ${GOPATH}/src/github.com

FROM ${base_image}

LABEL \
    org.opencontainers.image.name='Trivy' \
    org.opencontainers.image.description='Vulnerability and Misconfiguration Scanning.' \
    org.opencontainers.image.usage='https://github.com/aquasecurity/trivy' \
    org.opencontainers.image.url='https://www.aquasec.com/products/trivy/' \
    org.opencontainers.image.licenses='Apache License 2.0' \
    org.opencontainers.image.vendor='Aqua Security' \
    org.opencontainers.image.schema-version='0.72.0' \
    MAINTAINER="@rw"

RUN \
    apk add --no-cache clamav freshclam; \
    addgroup -g 65535 trivy; \
    adduser --shell /sbin/nologin --disabled-password -h /home/trivy --uid 65535 --ingroup trivy trivy

COPY --chown=trivy:trivy --from=build-env /contrib/*.tpl /home/trivy/
COPY --chown=trivy:trivy --from=build-env /usr/local/bin/go/bin/ /usr/local/bin

RUN \
    freshclam; \
    clamscan -rvi -l /home/trivy/last_scan.log --exclude-dir="^/sys|^/dev" /; \
    chown trivy:trivy /home/trivy/last_scan.log; \
    grep -Hrn FOUND /home/trivy/last_scan.log; \
    apk del clamav freshclam; \
    rm -rf /var/cache/apk/*

USER trivy
WORKDIR /home/trivy
