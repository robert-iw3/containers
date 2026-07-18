# syntax=docker/dockerfile:1
# boundary: provides access to applications and critical systems with fine-grained authorizations without managing credentials or exposing your network.
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

RUN apk add --no-cache \
    dumb-init \
    su-exec \
    iputils \
    libc6-compat \
    libcap \
    tzdata \
    wget

FROM base AS build-env

ENV PRODUCT_VERSION=0.21.3 \
    GPG_KEY=C874011F0AB405110D02105534365D9472D7468F

RUN apk add --no-cache -t .boundary-deps \
    ca-certificates \
    gnupg \
    openssl \
    unzip; \
    apkArch="$(apk --print-arch)"; \
    case "$apkArch" in \
      armhf) ARCH='arm' ;; \
      aarch64) ARCH='arm64' ;; \
      x86_64) ARCH='amd64' ;; \
      x86) ARCH='386' ;; \
      *) echo >&2 "error: unsupported architecture: $apkArch"; exit 1 ;; \
    esac; \
    found=''; \
    for server in \
      hkps://keys.openpgp.org \
      hkps://keyserver.ubuntu.com \
      hkps://pgp.mit.edu; do \
      echo "Fetching GPG key $GPG_KEY from $server"; \
      gpg --batch --keyserver "$server" --recv-keys "$GPG_KEY"; \
      found=yes && break; \
    done; \
    test -z "$found" && echo >&2 "error: failed to fetch GPG key $GPG_KEY" && exit 1; \
    mkdir -p /tmp/build; \
    cd /tmp/build; \
    wget --progress=bar:force https://releases.hashicorp.com/boundary/${PRODUCT_VERSION}/boundary_${PRODUCT_VERSION}_linux_${ARCH}.zip; \
    wget --progress=bar:force https://releases.hashicorp.com/boundary/${PRODUCT_VERSION}/boundary_${PRODUCT_VERSION}_SHA256SUMS; \
    wget --progress=bar:force https://releases.hashicorp.com/boundary/${PRODUCT_VERSION}/boundary_${PRODUCT_VERSION}_SHA256SUMS.sig; \
    gpg --batch --verify boundary_${PRODUCT_VERSION}_SHA256SUMS.sig boundary_${PRODUCT_VERSION}_SHA256SUMS; \
    grep boundary_${PRODUCT_VERSION}_linux_${ARCH}.zip boundary_${PRODUCT_VERSION}_SHA256SUMS | sha256sum -c; \
    unzip -d /tmp/build boundary_${PRODUCT_VERSION}_linux_${ARCH}.zip; \
    cp /tmp/build/boundary /bin/boundary; \
    rm -rf /tmp/build; \
    gpgconf --kill dirmngr; \
    gpgconf --kill gpg-agent; \
    apk del --purge .boundary-deps; \
    rm -rf /root/.gnupg /var/cache/apk/*

FROM base

LABEL org.opencontainers.image.name='HashiCorp Boundary' \
    org.opencontainers.image.description='Simple and secure remote access to hosts and critical systems.' \
    org.opencontainers.image.usage='https://developer.hashicorp.com/boundary/docs' \
    org.opencontainers.image.url='https://www.hashicorp.com/products/boundary' \
    org.opencontainers.image.vendor='HashiCorp' \
    org.opencontainers.image.licenses='Business Source License 1.1' \
    org.opencontainers.image.schema-version='0.21.3' \
    MAINTAINER="@rw"

RUN addgroup -g 65535 boundary && \
    adduser --shell /sbin/nologin --disabled-password -h /home/boundary --uid 65535 --ingroup boundary boundary && \
    mkdir -p /boundary/tls && \
    chown -R boundary:boundary /boundary && \
    chmod -R 750 /boundary

COPY --chown=boundary:boundary --from=build-env /bin/boundary /usr/local/bin/
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=boundary:boundary config.hcl /boundary/config.hcl

RUN boundary version

VOLUME /boundary
EXPOSE 9200 9201 9202 9203
USER boundary
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["server", "-config", "/boundary/config.hcl"]