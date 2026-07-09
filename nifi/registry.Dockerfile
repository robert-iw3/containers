# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash} as build
LABEL stage=build

RUN \
    apk add --no-cache \
        ca-certificates \
        openssl \
        curl \
        wget \
        unzip; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    rm -f /var/cache/apk/*

ARG UPSTREAM_VERSION=2.6.0
ARG MIRROR=https://dlcdn.apache.org

ENV PROJECT_BASE_DIR /opt/nifi-registry
ENV PROJECT_HOME ${PROJECT_BASE_DIR}/nifi-registry-${UPSTREAM_VERSION}

ENV UPSTREAM_BINARY_URL nifi/${UPSTREAM_VERSION}/nifi-registry-${UPSTREAM_VERSION}-bin.zip
ENV DOCKERIZE_VERSION v0.9.3

# Download, validate, and expand Apache NiFi-Registry binary.
RUN \
    mkdir -p ${PROJECT_BASE_DIR}; \
    curl -fSL ${MIRROR}/${UPSTREAM_BINARY_URL} -o ${PROJECT_BASE_DIR}/nifi-registry-${UPSTREAM_VERSION}-bin.zip; \
    echo "$(curl ${MIRROR}/${UPSTREAM_BINARY_URL}.sha512) *${PROJECT_BASE_DIR}/nifi-registry-${UPSTREAM_VERSION}-bin.zip" | sha512sum -c - ;\
    unzip ${PROJECT_BASE_DIR}/nifi-registry-${UPSTREAM_VERSION}-bin.zip -d ${PROJECT_BASE_DIR}; \
    rm ${PROJECT_BASE_DIR}/nifi-registry-${UPSTREAM_VERSION}-bin.zip; \
    rm -fr ${PROJECT_HOME}/docs; \
    \
    wget --progress=bar:force https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz; \
    tar -C /usr/local/bin -xzvf dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz; \
    rm dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN \
    apk --update add --no-cache \
        git \
        less \
        openssh \
        sshpass \
        bash \
        binutils \
        curl \
        fontconfig \
        ttf-dejavu \
        musl-locales \
        musl-locales-lang \
        musl-dev \
        tzdata \
        coreutils \
        grep \
        ca-certificates \
        p11-kit-trust \
        libgcc \
        libstdc++ \
        linux-headers \
        openssl \
        openjdk21 \
        openjdk21-jre \
        python3 \
        py3-virtualenv \
        jq \
        xmlstarlet \
        procps \
        procps-ng; \
  update-ca-certificates; \
  rm -rf /var/lib/apt/lists/*; \
  rm -f /var/cache/apk/*

LABEL \
      org.label-schema.docker.cmd='podman build -t nifi-registry -f registry.Dockerfile; podman run -p 18080:18080 --name nifi-registry -d nifi-registry'

ARG UPSTREAM_VERSION=2.6.0
ENV PROJECT_BASE_DIR /opt/nifi-registry
ENV PROJECT_HOME ${PROJECT_BASE_DIR}/nifi-registry-${UPSTREAM_VERSION}
ENV PROJECT_TEMPLATE_DIR ${PROJECT_BASE_DIR}/templates
ENV PROJECT_CONF_DIR ${PROJECT_HOME}/conf

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    TZ=UTC

ARG UID=1000
ARG GID=1000

RUN addgroup -g ${GID} nifi; \
    adduser -s /bin/bash -u ${UID} -G nifi -D nifi; \
    chown -R nifi:nifi ${PROJECT_BASE_DIR}; \
    mkdir -p ${PROJECT_BASE_DIR}

COPY --from=build --chown=nifi:nifi ${PROJECT_HOME} ${PROJECT_HOME}
COPY --from=build --chown=nifi:nifi /usr/local/bin/dockerize /usr/local/bin/dockerize
COPY ./templates ${PROJECT_TEMPLATE_DIR}
COPY registry-sh/ ${PROJECT_BASE_DIR}/scripts/

RUN mkdir -p ${PROJECT_HOME}/docs

# Web HTTP(s) ports
EXPOSE 18080 18443

WORKDIR ${PROJECT_HOME}
USER nifi

# Apply configuration and start NiFi Registry
CMD ${PROJECT_BASE_DIR}/scripts/start-plain.sh
# CMD ${PROJECT_BASE_DIR}/scripts/start.sh
