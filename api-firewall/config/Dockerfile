# Wallarm api-firewall: API Firewall is a high-performance proxy with API request and response validation based on OpenAPI and GraphQL schemas.
# It is designed to protect REST and GraphQL API endpoints in cloud-native environments.
# API Firewall provides API hardening with the use of a positive security model allowing calls that match a predefined API specification for requests and responses, while rejecting everything else.
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS build-env

ENV APIFIREWALL_VERSION=0.9.6 \
    GOPATH=/usr/local/bin/go \
    SNYK_API=

RUN \
    apk add --no-cache -t .api-deps \
        gcc \
        git \
        make \
        linux-headers \
        musl-dev \
        go; \
    \
    mkdir -p ${GOPATH}/src/github.com/api-firewall; \
    cd ${GOPATH}/src/github.com/api-firewall; \
    git clone --depth 1 --branch v${APIFIREWALL_VERSION} \
        https://github.com/wallarm/api-firewall; \
    cd api-firewall; \
    \
    cd cmd/api-firewall; \
    export GO111MODULE=on; \
    go install; \
    apk del --purge .api-deps; \
    ${GOPATH}/bin/api-firewall -v

FROM ${repo}/${base_image}@sha256:${image_hash}

COPY --chmod=755 --from=build-env /usr/local/bin/go/bin/ /usr/local/bin/
COPY --chmod=755 entrypoint.sh /entrypoint.sh

RUN \
    addgroup -g 65535 api-firewall; \
    adduser --shell /sbin/nologin --disabled-password -h /home/api-firewall --uid 65535 --ingroup api-firewall api-firewall; \
    apk add --no-cache -t .av-scan clamav freshclam; \
    freshclam; \
    clamscan -rvi -l /home/api-firewall/last_scan.log --exclude-dir="^/sys|^/dev" /; \
    chown api-firewall:api-firewall /home/api-firewall/last_scan.log; \
    grep -Hrn " FOUND" /home/api-firewall/last_scan.log; \
    apk del --purge .av-scan; \
    rm -rf /var/cache/apk/*

USER api-firewall
ENTRYPOINT [ "/entrypoint.sh" ]
