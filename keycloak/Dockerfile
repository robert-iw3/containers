# syntax=docker/dockerfile:1
# keycloak: Add authentication to applications and secure services with minimum effort.

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

LABEL org.opencontainers.image.name='Keycloak' \
    org.opencontainers.image.description='Open Source Identity and Access Management.' \
    org.opencontainers.image.usage='https://www.keycloak.org/guides' \
    org.opencontainers.image.url='https://www.keycloak.org/' \
    org.opencontainers.image.licenses='Apache License 2.0' \
    org.opencontainers.image.schema-version='26.6.4'

ARG BUILD_DATE
ARG VCS_REF
ARG OPENSSL_VERSION=3.5.7

RUN \
    apk add --no-cache \
        bash \
        curl \
        gcompat \
        openjdk17-jre \
        tar \
        which; \
    apk add --no-cache -t .fips-deps \
        make \
        gcc \
        libgcc \
        musl-dev \
        linux-headers \
        perl \
        wget; \
    wget https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz; \
    tar -zxvf openssl-${OPENSSL_VERSION}.tar.gz; \
    cd openssl-${OPENSSL_VERSION}; \
    ./Configure \
        enable-fips \
        --libdir=lib \
        --prefix=/usr; \
    make; \
    make install_fips; \
    apk del --no-network --purge .fips-deps; \
    rm -rf openssl-${OPENSSL_VERSION}.tar.gz openssl-${OPENSSL_VERSION}; \
    addgroup -g 65533 keycloak; \
    adduser --shell /sbin/nologin --disabled-password -h /home/keycloak --uid 65533 --ingroup keycloak keycloak

FROM base AS download

ARG VER=26.6.4

WORKDIR /src

RUN \
    apk add --no-cache -t .keycloak-deps ca-certificates wget; \
    wget -qO- https://github.com/keycloak/keycloak/releases/download/${VER}/keycloak-${VER}.tar.gz \
    | tar zx; \
    wget -qO- https://github.com/keycloak/keycloak/releases/download/${VER}/keycloak-${VER}.tar.gz.sha1; \
    grep keycloak-${VER}.tar.gz keycloak-${VER}.tar.gz.sha1 | sha1sum -c; \
    mkdir /opt/keycloak; \
    mv /src/keycloak-${VER}/* /opt/keycloak; \
    rm -rf /tmp/*; \
    apk del --purge .keycloak-deps; \
    rm -rf /var/cache/apk/*

FROM base

ENV JAVA_HOME="/usr/lib/jvm/java-17-openjdk"

COPY --chown=keycloak:keycloak --from=download /opt/keycloak /opt/keycloak
COPY --chown=keycloak:keycloak keycloak.conf /opt/keycloak/conf
COPY --chmod=755 generate-ssl.sh /home/keycloak

RUN \
    echo "networkaddress.cache.ttl=5" >> "${JAVA_HOME}/conf/security/java.security"; \
    echo "fips.provider.7=XMLDSig" >> "${JAVA_HOME}/conf/security/java.security"; \
    sed --in-place --expression="s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" "${JAVA_HOME}/conf/security/java.security"; \
    bash -c "/home/keycloak/generate-ssl.sh"; \
    chmod +x /opt/keycloak/bin/kc.sh; \
    rm -rf /var/cache/apk/*; \
    chown -R keycloak:keycloak /home/keycloak /opt/keycloak; \
    chmod -R 750 /opt/keycloak; \
    /opt/keycloak/bin/kc.sh build --features=fips --fips-mode=strict

EXPOSE 8080 8443
USER keycloak
WORKDIR /home/keycloak
HEALTHCHECK --timeout=3s --start-period=60s --retries=5 \
   CMD curl -fs http://localhost:8080/health/ready || curl -fsk https://localhost:8443/health/ready || exit 1
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized", "--https-port=8443", "--db-pool-max-size=20"]