# syntax=docker/dockerfile:1
# sonarqube: clean code for teams and enterprises.
ARG repo="quay.io/almalinuxorg" \
    base_image="10-minimal" \
    image_hash="dbe9e629bda941bbc557666cb8fcc184b0ce40e92eaff66eaca2aefde9e5ac35"

FROM ${repo}/${base_image}@sha256:${image_hash} AS builder

ARG SONARQUBE_VERSION="25.11.0.114957"
ARG SONARQUBE_ZIP_URL="https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-${SONARQUBE_VERSION}.zip"

ENV SONARQUBE_HOME="/opt/sonarqube" \
    SONAR_VERSION="${SONARQUBE_VERSION}" \
    SQ_DATA_DIR="/opt/sonarqube/data" \
    SQ_EXTENSIONS_DIR="/opt/sonarqube/extensions" \
    SQ_LOGS_DIR="/opt/sonarqube/logs" \
    SQ_TEMP_DIR="/opt/sonarqube/temp"

RUN \
    microdnf update -y; \
    microdnf install -y \
        bash \
        wget \
        unzip

WORKDIR /opt

RUN \
    for server in $(shuf -e hkps://keys.openpgp.org \
                            hkps://keyserver.ubuntu.com \
                            hkps://pgp.mit.edu) ; do \
        gpg --batch --keyserver "${server}" --recv-keys 679F1EE92B19609DE816FDE81DB198F93525EC1A && break || : ; \
    done; \
    wget --progress=bar:force -O sonarqube.zip ${SONARQUBE_ZIP_URL}; \
    wget -O sonarqube.zip.asc ${SONARQUBE_ZIP_URL}.asc; \
    gpg --batch --verify sonarqube.zip.asc sonarqube.zip; \
    unzip -q sonarqube.zip; \
    mv sonarqube-${SONARQUBE_VERSION} sonarqube; \
    rm -f sonarqube.zip*; \
    rm -rf ${SONARQUBE_HOME}/bin/*; \
    ln -s "${SONARQUBE_HOME}/lib/sonar-application-${SONARQUBE_VERSION}.jar" "${SONARQUBE_HOME}/lib/sonarqube.jar"; \
    \
    chmod -R 555 ${SONARQUBE_HOME}; \
    chmod -R ugo+wrX ${SQ_DATA_DIR} ${SQ_EXTENSIONS_DIR} ${SQ_LOGS_DIR} ${SQ_TEMP_DIR}

# Use "distroless" as minimal base image to package sonarqube java libs
# See https://github.com/GoogleContainerTools/distroless for details
# as small an image size as java can get
FROM gcr.io/distroless/java17-debian12:nonroot
COPY --chown=65532:65532 --from=builder /opt/sonarqube /opt/sonarqube
VOLUME [ "/opt/sonarqube/data", "/opt/sonarqube/extensions", "/opt/sonarqube/logs", "/opt/sonarqube/temp" ]
EXPOSE 9000
USER 65532:65532
ENTRYPOINT [ "java", "-jar", "/opt/sonarqube/lib/sonarqube.jar", "-Dsonar.log.console=true" ]
LABEL \
    org.opencontainers.image.name='SonarQube' \
    org.opencontainers.image.description='Clean code for teams and enterprises.' \
    org.opencontainers.image.usage='https://docs.sonarqube.org/latest/' \
    org.opencontainers.image.url='https://www.sonarsource.com/products/sonarqube/' \
    org.opencontainers.image.licenses='GNU Lesser General Public License v3.0' \
    org.opencontainers.image.vendor='Sonar' \
    org.opencontainers.image.schema-version='25.11.0.114957'
