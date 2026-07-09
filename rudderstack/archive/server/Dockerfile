# syntax=docker/dockerfile:1
ARG GO_VERSION=1.21.3
ARG ALPINE_VERSION=3.18

FROM docker.io/golang:${GO_VERSION}-alpine${ALPINE_VERSION} AS builder

ARG VERSION
ARG REVISION
ARG COMMIT_HASH
ARG ENTERPRISE_TOKEN
ARG RACE_ENABLED=false
ARG CGO_ENABLED=0
ARG PKG_NAME=github.com/rudderlabs/release-demo

RUN \
    apk add --update --no-cache \
        make \
        tzdata \
        ca-certificates \
        git

WORKDIR /rudder-server

RUN \
    git clone https://github.com/rudderlabs/rudder-server.git; \
    cp rudder-server/go.mod .; \
    cp rudder-server/go.sum .; \
    go mod download; \
    mv rudder-server/* .; \
    BUILD_DATE=$(date "+%F,%T") \
    LDFLAGS="-s -w -X main.version=${VERSION} -X main.commit=${COMMIT_HASH} -X main.buildDate=$BUILD_DATE -X main.builtBy=${REVISION} -X main.builtBy=${REVISION} -X main.enterpriseToken=${ENTERPRISE_TOKEN} " \
    make build; \
    go build -o devtool ./cmd/devtool/; \
    go build -o rudder-cli ./cmd/rudder-cli/

FROM alpine:${ALPINE_VERSION}

RUN \
    apk --no-cache upgrade; \
    apk --no-cache add --no-cache \
        tzdata \
        ca-certificates \
        postgresql-client \
        curl \
        bash

COPY --from=builder rudder-server/rudder-server .
COPY --from=builder rudder-server/build/wait-for-go/wait-for-go .
COPY --from=builder rudder-server/build/regulation-worker .
COPY --from=builder rudder-server/devtool .
COPY --from=builder rudder-server/rudder-cli /usr/bin/rudder-cli
COPY --from=builder rudder-server/build/docker-entrypoint.sh .
COPY --from=builder rudder-server/build/wait-for .
COPY --from=builder rudder-server/scripts/generate-event /scripts/generate-event
COPY --from=builder rudder-server/scripts/batch.json /scripts/batch.json

EXPOSE 8080/tcp
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["/rudder-server"]