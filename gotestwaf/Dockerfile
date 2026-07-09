# gotestwaf: GoTestWAF is a tool for API and OWASP attack simulation that supports a wide range of API protocols including REST, GraphQL, gRPC, WebSockets, SOAP, XMLRPC, and others.
# It was designed to evaluate web application security solutions, such as API security proxies, Web Application Firewalls, IPS, API gateways, and others.
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS build-env

ENV GOPATH=/usr/local/bin/go \
    SNYK_API=

RUN \
    apk add --no-cache -t .gotestwaf-deps \
        gcc \
        git \
        make \
        linux-headers \
        musl-dev \
        go \
        npm; \
    mkdir -p ${GOPATH}/src/github.com/gotestwaf; \
    cd ${GOPATH}/src/github.com/gotestwaf; \
    git clone https://github.com/wallarm/gotestwaf.git; \
    cd gotestwaf; \
    cp -R testcases /; \
#    npm install -g snyk; \
#    npm install -g snyk-to-html; \
#    snyk config set api=${SNYK_API}; \
#    snyk code test --json | snyk-to-html -o /gotestwaf-code-review.html; \
#    snyk test --all-projects --json | snyk-to-html -o /gotestwaf-deps.html; \
#    snyk monitor; \
#    npm uninstall -g snyk; \
#    npm uninstall -g snyk-to-html; \
    cd cmd/gotestwaf; \
    export GO111MODULE=on; \
    go install; \
    apk del --purge --no-network .gotestwaf-deps

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN \
    apk add --no-cache \
        tini \
        chromium \
        font-inter \
        font-iosevka \
        fontconfig \
        clamav \
        freshclam; \
    fc-cache -fv; \
    mkdir -p /app/reports; \
    mkdir -p /app/testcases; \
    mkdir -p /app/.config/gotestwaf; \
    chmod 777 /app/reports

WORKDIR /app

#COPY --from=build-env /gotestwaf-code-review.html .
#COPY --from=build-env /gotestwaf-deps.html .
COPY --chmod=755 --from=build-env /usr/local/bin/go/bin/ .
COPY --from=build-env /testcases/ testcases/
COPY ./config.yaml ./config.yaml

RUN \
    freshclam; \
    clamscan -rvi -l last_scan.log --exclude-dir="^/sys|^/dev" /; \
    grep -Hrn " FOUND" last_scan.log; \
    apk del --purge --no-network clamav freshclam; \
    rm -rf /var/cache/apk/*

VOLUME [ "/app/reports" ]
ENTRYPOINT [ "/sbin/tini", "--", "/app/gotestwaf" ]
