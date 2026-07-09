# syntax=docker/dockerfile:1
# Apache NiFi: A powerful, open-source tool for automating data flows between systems.
ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash}

ARG UID=1001
ARG GID=1001
ARG NIFI_VERSION=2.4.0
ARG BASE_URL=https://archive.apache.org/dist
ARG MIRROR_BASE_URL=${MIRROR_BASE_URL:-${BASE_URL}}
ARG DISTRO_PATH=${DISTRO_PATH:-${NIFI_VERSION}}
ARG NIFI_BINARY_PATH=${NIFI_BINARY_PATH:-nifi/${DISTRO_PATH}/nifi-${NIFI_VERSION}-bin.zip}
ARG NIFI_TOOLKIT_BINARY_PATH=${NIFI_TOOLKIT_BINARY_PATH:-nifi/${DISTRO_PATH}/nifi-toolkit-${NIFI_VERSION}-bin.zip}

ENV NIFI_BASE_DIR=/opt/nifi
ENV NIFI_HOME ${NIFI_BASE_DIR}/nifi-current
ENV NIFI_TOOLKIT_HOME ${NIFI_BASE_DIR}/nifi-toolkit-current
ENV NIFI_PID_DIR=${NIFI_HOME}/run
ENV NIFI_LOG_DIR=${NIFI_HOME}/logs
ENV PATH=/home/nifi/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    TZ=UTC

RUN \
    /bin/sh -c set -eux; \
    apk add --no-cache \
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
        procps-ng \
        unzip; \
    rm -rf /var/cache/apk/*; \
    mkdir -p ${NIFI_BASE_DIR}

COPY --chmod=755 sh/ ${NIFI_BASE_DIR}/scripts/

# Setup NiFi user and create necessary directories
RUN \
    addgroup -g ${GID} nifi; \
    adduser -h /home/nifi --shell /bin/bash --disabled-password --uid ${UID} --ingroup nifi --gecos '' nifi; \
    chown -R nifi:nifi ${NIFI_BASE_DIR}

USER nifi

# Download, validate, and expand Apache NiFi Toolkit binary.
RUN \
    curl -LsSf https://astral.sh/uv/install.sh | sh; \
    curl -fSL ${MIRROR_BASE_URL}/${NIFI_TOOLKIT_BINARY_PATH} -o ${NIFI_BASE_DIR}/nifi-toolkit-${NIFI_VERSION}-bin.zip; \
    echo "$(curl ${BASE_URL}/${NIFI_TOOLKIT_BINARY_PATH}.sha512) *${NIFI_BASE_DIR}/nifi-toolkit-${NIFI_VERSION}-bin.zip" | sha512sum -c - ;\
    unzip ${NIFI_BASE_DIR}/nifi-toolkit-${NIFI_VERSION}-bin.zip -d ${NIFI_BASE_DIR} ;\
    rm ${NIFI_BASE_DIR}/nifi-toolkit-${NIFI_VERSION}-bin.zip ;\
    mv ${NIFI_BASE_DIR}/nifi-toolkit-${NIFI_VERSION} ${NIFI_TOOLKIT_HOME} ;\
    ln -s ${NIFI_TOOLKIT_HOME} ${NIFI_BASE_DIR}/nifi-toolkit-${NIFI_VERSION} ;\
    \
# Download, validate, and expand Apache NiFi binary.
    curl -fSL ${MIRROR_BASE_URL}/${NIFI_BINARY_PATH} -o ${NIFI_BASE_DIR}/nifi-${NIFI_VERSION}-bin.zip ;\
    echo "$(curl ${BASE_URL}/${NIFI_BINARY_PATH}.sha512) *${NIFI_BASE_DIR}/nifi-${NIFI_VERSION}-bin.zip" | sha512sum -c - ;\
    unzip ${NIFI_BASE_DIR}/nifi-${NIFI_VERSION}-bin.zip -d ${NIFI_BASE_DIR} ;\
    rm ${NIFI_BASE_DIR}/nifi-${NIFI_VERSION}-bin.zip ;\
    mv ${NIFI_BASE_DIR}/nifi-${NIFI_VERSION} ${NIFI_HOME} ;\
    mkdir -p ${NIFI_HOME}/conf ;\
    mkdir -p ${NIFI_HOME}/database_repository ;\
    mkdir -p ${NIFI_HOME}/flowfile_repository ;\
    mkdir -p ${NIFI_HOME}/content_repository ;\
    mkdir -p ${NIFI_HOME}/provenance_repository ;\
    mkdir -p ${NIFI_HOME}/python_extensions ;\
    mkdir -p ${NIFI_HOME}/nar_extensions ;\
    mkdir -p ${NIFI_HOME}/state ;\
    mkdir -p ${NIFI_HOME}/templates ;\
    mkdir -p ${NIFI_LOG_DIR} ;\
    ln -s ${NIFI_HOME} ${NIFI_BASE_DIR}/nifi-${NIFI_VERSION}

VOLUME ${NIFI_LOG_DIR} \
       ${NIFI_HOME}/conf \
       ${NIFI_HOME}/database_repository \
       ${NIFI_HOME}/flowfile_repository \
       ${NIFI_HOME}/content_repository \
       ${NIFI_HOME}/provenance_repository \
       ${NIFI_HOME}/python_extensions \
       ${NIFI_HOME}/nar_extensions \
       ${NIFI_HOME}/state \
       ${NIFI_HOME}/templates

# Clear nifi-env.sh in favour of configuring all environment variables in the Dockerfile
RUN echo "#!/bin/sh\n" > $NIFI_HOME/bin/nifi-env.sh

# Web HTTP(s) & Socket Site-to-Site Ports
EXPOSE 8443/tcp 10000/tcp 8000/tcp

WORKDIR ${NIFI_HOME}

COPY templates/ ${NIFI_HOME}/templates/
ENTRYPOINT ["../scripts/start.sh"]
