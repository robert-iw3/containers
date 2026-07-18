# syntax=docker/dockerfile:1
# terraform: infrastructure as code for provisioning the hashicorp stack.
# Used to drive plan/apply AND to validate the roots in this directory
# (see scripts/validate.sh).
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    openssh-client \
    openssl \
    tzdata

FROM base AS build-env

ENV TERRAFORM_VER=1.15.8 \
    GPG_KEY=C874011F0AB405110D02105534365D9472D7468F

RUN apk add --no-cache -t .build-deps \
    gnupg \
    unzip \
    wget; \
    apkArch="$(apk --print-arch)"; \
    case "$apkArch" in \
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
    wget --progress=bar:force https://releases.hashicorp.com/terraform/${TERRAFORM_VER}/terraform_${TERRAFORM_VER}_linux_${ARCH}.zip; \
    wget --progress=bar:force https://releases.hashicorp.com/terraform/${TERRAFORM_VER}/terraform_${TERRAFORM_VER}_SHA256SUMS; \
    wget --progress=bar:force https://releases.hashicorp.com/terraform/${TERRAFORM_VER}/terraform_${TERRAFORM_VER}_SHA256SUMS.sig; \
    gpg --batch --verify terraform_${TERRAFORM_VER}_SHA256SUMS.sig terraform_${TERRAFORM_VER}_SHA256SUMS; \
    grep terraform_${TERRAFORM_VER}_linux_${ARCH}.zip terraform_${TERRAFORM_VER}_SHA256SUMS | sha256sum -c; \
    unzip -d /tmp/build terraform_${TERRAFORM_VER}_linux_${ARCH}.zip; \
    cp /tmp/build/terraform /bin/terraform; \
    rm -rf /tmp/build; \
    gpgconf --kill dirmngr; \
    gpgconf --kill gpg-agent; \
    apk del --no-network --purge .build-deps; \
    rm -rf /root/.gnupg /var/cache/apk/*

FROM base

LABEL org.opencontainers.image.name='HashiCorp Terraform' \
    org.opencontainers.image.description='Infrastructure automation to provision and manage resources in any cloud or data center.' \
    org.opencontainers.image.usage='https://developer.hashicorp.com/terraform/docs' \
    org.opencontainers.image.url='https://www.hashicorp.com/products/terraform' \
    org.opencontainers.image.vendor='HashiCorp' \
    org.opencontainers.image.licenses='Business Source License 1.1' \
    org.opencontainers.image.schema-version='1.15.8' \
    MAINTAINER="@rw"

COPY --from=build-env /bin/terraform /usr/local/bin/terraform

# stays root: under rootless podman this maps to the invoking host user, so
# files written into the mounted workspace keep the caller's ownership
RUN terraform version; \
    mkdir -p /tfcache /workspace
ENV TF_PLUGIN_CACHE_DIR=/tfcache \
    TF_IN_AUTOMATION=1

WORKDIR /workspace
ENTRYPOINT ["terraform"]
