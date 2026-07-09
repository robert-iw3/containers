# syntax=docker/dockerfile:1

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f" \
    runtime_repo="docker.io" \
    runtime_image="busybox:glibc" \
    runtime_hash="1cfa4e2b09e127b9c4ed43578d3f3c18e7d44ea47b9ea98475c0cbe9086525f8"

FROM ${repo}/${base_image}@sha256:${image_hash} AS build

RUN apk add --no-cache ca-certificates git openssl

ENV PATH /usr/local/go/bin:$PATH
ENV GOLANG_VERSION 1.26.5

# Install Go from source for supported architectures
RUN set -eux; \
    apk add --no-cache --virtual .fetch-deps gnupg; \
    arch="$(apk --print-arch)"; \
    case "$arch" in \
        'x86_64') export GOARCH='amd64' GOOS='linux'; ;; \
        'armhf') export GOARCH='arm' GOARM='6' GOOS='linux'; ;; \
        'armv7') export GOARCH='arm' GOARM='7' GOOS='linux'; ;; \
        'aarch64') export GOARCH='arm64' GOOS='linux'; ;; \
        'x86') export GO386='softfloat' GOARCH='386' GOOS='linux'; ;; \
        'ppc64le') export GOARCH='ppc64le' GOOS='linux'; ;; \
        'riscv64') export GOARCH='riscv64' GOOS='linux'; ;; \
        's390x') export GOARCH='s390x' GOOS='linux'; ;; \
        *) echo >&2 "error: unsupported architecture '$arch'"; exit 1 ;; \
    esac; \
    url="https://dl.google.com/go/go${GOLANG_VERSION}.src.tar.gz"; \
    sha256='495be4bc87176ac567392e5b4116abd98466d33d7b49d41e764ccc6976b2dc42'; \
    wget -O go.tgz.asc "$url.asc"; \
    wget -O go.tgz "$url"; \
    echo "$sha256 *go.tgz" | sha256sum -c -; \
    GNUPGHOME="$(mktemp -d)"; export GNUPGHOME; \
    gpg --batch --keyserver keyserver.ubuntu.com --recv-keys 'EB4C 1BFD 4F04 2F6D DDCC EC91 7721 F63B D38B 4796'; \
    gpg --batch --verify go.tgz.asc go.tgz; \
    gpgconf --kill all; \
    rm -rf "$GNUPGHOME" go.tgz.asc; \
    tar -C /usr/local -xzf go.tgz; \
    rm go.tgz; \
    apk add --no-cache --virtual .build-deps bash gcc musl-dev; \
    export GOCACHE='/tmp/gocache'; \
    ( cd /usr/local/go/src; \
      export GOROOT_BOOTSTRAP="$(go env GOROOT)" GOHOSTOS="$GOOS" GOHOSTARCH="$GOARCH"; \
      if [ "${GOARCH:-}" = '386' ]; then export CGO_CFLAGS='-fno-stack-protector'; fi; \
      ./make.bash; \
    ); \
    apk del --no-network .build-deps .fetch-deps; \
    rm -rf /usr/local/go/pkg/*/cmd /usr/local/go/pkg/bootstrap /usr/local/go/pkg/obj \
           /usr/local/go/pkg/tool/*/api /usr/local/go/pkg/tool/*/go_bootstrap \
           /usr/local/go/src/cmd/dist/dist "$GOCACHE"; \
    go version

ENV GOPATH /go
ENV PATH $GOPATH/bin:$PATH
RUN mkdir -p "$GOPATH/src" "$GOPATH/bin" && chmod -R 1777 "$GOPATH"

ENV AGENT_VERSION="1.20.3"
WORKDIR /app
RUN git clone --depth 1 --branch "${AGENT_VERSION}" https://github.com/middleware-labs/mw-agent; \
    cd mw-agent; \
    CGO_ENABLED=0; \
    go get -d -v ./...; \
    go mod tidy

RUN cd mw-agent; \
    CGO_ENABLED=0 go build -ldflags "-s -w -X main.agentVersion=${AGENT_VERSION}" -o /tmp/mw-agent cmd/host-agent/main.go

FROM ${runtime_repo}/${runtime_image}@sha256:${runtime_hash}
RUN adduser -D -u 1001 mw-agent && mkdir -p /var/log && chown mw-agent /var/log
WORKDIR /opt/mw-host-agent
USER 1001
COPY --from=build --chown=mw-agent /etc/ssl/certs /etc/ssl/certs
COPY --from=build --chown=mw-agent /tmp/mw-agent /opt/mw-host-agent/mw-agent
COPY --from=build --chown=mw-agent /app/mw-agent/configyamls-k8s/otel-config.yaml /etc/mw-agent/otel-config.yaml
CMD ["/opt/mw-host-agent/mw-agent", "start"]