ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

RUN \
    apk add --no-cache \
        bash \
        curl \
        libcap \
        su-exec \
        dumb-init \
        procps \
        tzdata \
        openssl \
        python3 \
        py3-pip

FROM base AS build-env

ENV VAULT_VER=2.0.3 \
    VAULT_GPGKEY=C874011F0AB405110D02105534365D9472D7468F

RUN \
    apk add --no-cache -t .vault-deps \
        ca-certificates \
        gnupg \
        unzip \
        wget; \
    apkArch="$(apk --print-arch)"; \
    case "$apkArch" in armhf) ARCH='arm' ;; \
      aarch64) ARCH='arm64' ;; \
      x86_64) ARCH='amd64' ;; \
      x86) ARCH='386' ;; \
      *) echo >&2 "error: unsupported architecture: $apkArch"; \
      exit 1 ;; \
    esac; \
    found=''; \
    for server in \
      hkps://keys.openpgp.org \
      hkps://keyserver.ubuntu.com \
      hkps://pgp.mit.edu; do \
      echo "Fetching GPG key $VAULT_GPGKEY from $server"; \
      gpg --batch --keyserver "$server" --recv-keys "$VAULT_GPGKEY"; \
      found=yes && break; \
    done; \
    test -z "$found" && echo >&2 "error: failed to fetch GPG key $VAULT_GPGKEY" && exit 1; \
    mkdir -p /tmp/build; \
    cd /tmp/build; \
    wget --progress=bar:force https://releases.hashicorp.com/vault/${VAULT_VER}/vault_${VAULT_VER}_linux_${ARCH}.zip; \
    wget --progress=bar:force https://releases.hashicorp.com/vault/${VAULT_VER}/vault_${VAULT_VER}_SHA256SUMS; \
    wget --progress=bar:force https://releases.hashicorp.com/vault/${VAULT_VER}/vault_${VAULT_VER}_SHA256SUMS.sig; \
    gpg --batch --verify vault_${VAULT_VER}_SHA256SUMS.sig vault_${VAULT_VER}_SHA256SUMS; \
    grep vault_${VAULT_VER}_linux_${ARCH}.zip vault_${VAULT_VER}_SHA256SUMS | sha256sum -c; \
    unzip -d /tmp/build vault_${VAULT_VER}_linux_${ARCH}.zip; \
    cp /tmp/build/vault /bin/vault; \
    rm -rf /tmp/build; \
    gpgconf --kill dirmngr; \
    gpgconf --kill gpg-agent; \
    apk del --no-network --purge .vault-deps; \
    rm -rf /root/.gnupg /var/cache/apk/*; \
    /bin/vault version

FROM base

LABEL org.opencontainers.image.name='HashiCorp Vault' \
    org.opencontainers.image.description='Vault is an identity-based secret and encryption management system.' \
    org.opencontainers.image.usage='https://developer.hashicorp.com/vault/docs' \
    org.opencontainers.image.url='https://www.hashicorp.com/products/vault' \
    org.opencontainers.image.vendor='HashiCorp' \
    org.opencontainers.image.licenses='Mozilla Public License 2.0' \
    org.opencontainers.image.schema-version='1.21.0' \
    MAINTAINER="@rw"

RUN \
    addgroup -g 65535 vault; \
    adduser --shell /sbin/nologin --disabled-password -h /home/vault --uid 65535 --ingroup vault vault; \
    mkdir -p /vault/data; \
    mkdir -p /vault/logs; \
    mkdir -p /vault/policies; \
    mkdir -p /vault/config; \
    mkdir -p /certs; \
    chown -R vault:vault /vault; \
    chown -R vault:vault /certs; \
    chgrp -R 0 /vault; \
    chgrp -R 0 /certs; \
    chmod -R g+rwX /vault; \
    chmod -R g+rwX /certs

COPY --chown=vault:vault --from=build-env /bin/vault /usr/local/bin/
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

VOLUME /vault/logs
VOLUME /vault/policies
VOLUME /vault/data
VOLUME /certs
EXPOSE 8200/tcp 8201/tcp
USER vault
ENTRYPOINT ["entrypoint.sh"]
CMD ["vault", "server", "-config=/vault/config/vault-server.hcl"]