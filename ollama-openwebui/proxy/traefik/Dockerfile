# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="483f502c0e6aff6d80a807f25d3f88afa40439c29fdd2d21a0912e0f42db842a"

FROM ${repo}/${base_image}@sha256:${image_hash} AS bin-download

ARG TRAEFIK_VER=3.3.2

RUN \
    apk --no-cache add \
        ca-certificates \
        tzdata; \
	apkArch="$(apk --print-arch)"; \
	case "$apkArch" in \
		armhf) arch='armv6' ;; \
		aarch64) arch='arm64' ;; \
		x86_64) arch='amd64' ;; \
		s390x) arch='s390x' ;; \
		*) echo >&2 "error: unsupported architecture: $apkArch"; exit 1 ;; \
	esac; \
	wget --quiet -O /tmp/traefik.tar.gz "https://github.com/traefik/traefik/releases/download/v${TRAEFIK_VER}/traefik_v${TRAEFIK_VER}_linux_$arch.tar.gz"; \
	tar xzvf /tmp/traefik.tar.gz -C /usr/local/bin traefik; \
	rm -f /tmp/traefik.tar.gz


# Use distroless as minimal base image to package traefik binary
# See https://github.com/GoogleContainerTools/distroless for details
FROM gcr.io/distroless/static:debug
SHELL ["/busybox/sh", "-c"]
RUN mkdir -p /etc/traefik/dynamic; \
    mkdir -p /traefik/certs; \
    mkdir -p /var/log/traefik
COPY --chmod=755 --from=bin-download /usr/local/bin/traefik /usr/local/bin/traefik
COPY config/traefik.yml /
COPY config/tls.yml /etc/traefik/dynamic
COPY /certs /traefik/certs
ENTRYPOINT ["/usr/local/bin/traefik"]
