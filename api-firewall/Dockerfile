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

# Sane production defaults, overridable at runtime (compose passes .env
# through; see .env.example). Full reference:
# https://docs.wallarm.com/api-firewall/configuration-guides/
ENV APIFW_MODE=PROXY \
    APIFW_URL=http://0.0.0.0:8080 \
    APIFW_HEALTH_HOST=0.0.0.0:9667 \
    APIFW_API_SPECS=/opt/resources/api-spec.json \
    APIFW_SERVER_URL=http://demo-backend:8080 \
    APIFW_REQUEST_VALIDATION=BLOCK \
    APIFW_RESPONSE_VALIDATION=LOG_ONLY \
    APIFW_CUSTOM_BLOCK_STATUS_CODE=403 \
    APIFW_LOG_LEVEL=INFO \
    APIFW_LOG_FORMAT=JSON \
    APIFW_TLS_CERTS_PATH=/opt/resources/certs \
    APIFW_TLS_CERT_FILE=api-fw.crt.pem \
    APIFW_TLS_CERT_KEY=api-fw.key.pem \
    APIFW_METRICS_ENABLED=true \
    APIFW_METRICS_HOST=0.0.0.0:9010

USER api-firewall

# Liveness probe against the health listener (APIFW_HEALTH_HOST, :9667).
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=10s \
    CMD [ "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:9667/v1/liveness" ]

ENTRYPOINT [ "/entrypoint.sh" ]
