# syntax=docker/dockerfile:1
# opensearch data-prepper: a server-side data collector capable of filtering, enriching, transforming, normalizing,
# and aggregating data for downstream analytics and visualization.

ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL \
    org.opencontainers.image.name='OpenSearch Data-Prepper' \
    org.opencontainers.image.description='A server-side data collector.' \
    org.opencontainers.image.usage='https://opensearch.org/docs/latest/data-prepper/index/' \
    org.opencontainers.image.url='https://github.com/opensearch-project/data-prepper' \
    org.opencontainers.image.licenses='Apache License 2.0' \
    org.opencontainers.image.vendor='OpenSearch' \
    org.opencontainers.image.schema-version='2.12.0' \
    MAINTAINER="@rw"

ARG VERSION="2.12.0"
ARG URL="https://artifacts.opensearch.org/data-prepper/${VERSION}/opensearch-data-prepper-${VERSION}-linux-x64.tar.gz"
ENV JAVA_HOME="/usr/lib/jvm/java-17-temurin"
ENV DATA_PREPPER_PATH="/usr/share/data-prepper"
ENV TINI_VERSION="v0.19.0"
#ENV SNYK_API=" "

RUN \
    apk add --no-cache \
        bash \
        ca-certificates \
        wget; \
    addgroup -g 1001 dataprepper; \
    adduser --shell /sbin/nologin --disabled-password -h /home/dataprepper --uid 1001 --ingroup dataprepper dataprepper; \
# temurin download
     \
    wget https://packages.adoptium.net/artifactory/api/security/keypair/public/repositories/apk \
    -O /etc/apk/keys/adoptium.rsa.pub; \
    echo '@edge http://dl-cdn.alpinelinux.org/alpine/edge/main' >> /etc/apk/repositories; \
    echo 'https://packages.adoptium.net/artifactory/apk/alpine/main' >> /etc/apk/repositories; \
    apk update; apk upgrade; \
    apk add --no-cache temurin-17-jdk; \
    echo "networkaddress.cache.ttl=5" >> "${JAVA_HOME}/conf/security/java.security"; \
    sed --in-place --expression="s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" "${JAVA_HOME}/conf/security/java.security"; \
# data-prepper download
    \
    wget "${URL}" -O /tmp/opensearch-data-prepper-${VERSION}.tar.gz; \
    tar zxvf /tmp/opensearch-data-prepper-${VERSION}.tar.gz; \
    mkdir -p "${DATA_PREPPER_PATH}" /var/log/data-prepper; \
    mv /opensearch-data-prepper-${VERSION}-linux-x64/* "${DATA_PREPPER_PATH}"

# example of adding your configs for data-prepper to use during runtime
ADD config/data-prepper-config.yaml "${DATA_PREPPER_PATH}"/config
ADD config/default-keystore.p12 "${DATA_PREPPER_PATH}"
ADD config/pipelines.yaml "${DATA_PREPPER_PATH}"/pipelines
COPY --chmod=755 scan_jars.sh "${DATA_PREPPER_PATH}"


RUN \
# perms
    chown -R dataprepper:dataprepper "${DATA_PREPPER_PATH}" "${JAVA_HOME}"; \
    chmod -R a+rwx,o-rwx "${DATA_PREPPER_PATH}" "${JAVA_HOME}"; \
# av/deps scans
    \
    apk add --no-cache -t .scan \
        clamav \
        freshclam \
        npm; \
    freshclam; \
    clamscan -rvi -l /home/dataprepper/clamav_scan.log --exclude-dir="^/sys|^/dev" / || : ; \
    \
# snyk jar scans
#    npm install -g snyk; \
#    snyk config set api=${SNYK_API}; \
#    cd ${DATA_PREPPER_PATH}/lib; \
#    bash -c "${DATA_PREPPER_PATH}/scan_jars.sh"; \
#    npm uninstall -g snyk; \
    \
# cleanup
    apk del --no-network --purge .scan; \
    rm -rf /var/cache/apk/* /tmp/* /var/tmp/*; \
    \
# tini bin download
    tini_bin="" ; \
    case "$(arch)" in \
        aarch64) tini_bin='tini-arm64' ;; \
        x86_64)  tini_bin='tini-amd64' ;; \
        *) echo >&2 ; echo >&2 "Unsupported architecture $(arch)" ; echo >&2 ; exit 1 ;; \
    esac ; \
    curl --retry 10 -S -L -O https://github.com/krallin/tini/releases/download/${TINI_VERSION}/${tini_bin} ; \
    curl --retry 10 -S -L -O https://github.com/krallin/tini/releases/download/${TINI_VERSION}/${tini_bin}.sha256sum ; \
    sha256sum -c ${tini_bin}.sha256sum ; \
    rm ${tini_bin}.sha256sum ; \
    mv ${tini_bin} /usr/bin/tini ; \
    chmod 0555 /usr/bin/tini

ENV PATH="${PATH}:${JAVA_HOME}/bin"
USER dataprepper
WORKDIR "${DATA_PREPPER_PATH}"
ENTRYPOINT [ "/usr/bin/tini", "--" ]
CMD [ "bin/data-prepper" ]
