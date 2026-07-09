# syntax=docker/dockerfile:1.4
# coredns: CoreDNS is a fast and flexible DNS server.

ARG DEBIAN_IMAGE=docker.io/golang:bookworm
ARG BASE=gcr.io/distroless/static-debian12:nonroot

FROM --platform=$BUILDPLATFORM ${DEBIAN_IMAGE} AS build

RUN \
    export DEBCONF_NONINTERACTIVE_SEEN=true \
           DEBIAN_FRONTEND=noninteractive \
           DEBIAN_PRIORITY=critical \
           TERM=linux; \
    apt-get -qq update; \
    apt-get -yyqq upgrade; \
    apt-get -yyqq install \
        ca-certificates \
        libcap2-bin \
        git \
        make; \
    apt-get clean; \
    git clone https://github.com/coredns/coredns; \
    cd coredns; \
    make; \
    setcap cap_net_bind_service=+ep /go/coredns/coredns

FROM --platform=$TARGETPLATFORM ${BASE}
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build /go/coredns/coredns /coredns
USER nonroot:nonroot
WORKDIR /
EXPOSE 53 53/udp
ENTRYPOINT ["/coredns"]