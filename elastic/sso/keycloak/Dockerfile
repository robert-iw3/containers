# syntax=docker/dockerfile:1.4
# keycloak: Add authentication to applications and secure services with minimum effort.

ARG fetcher_image="registry.access.redhat.com/ubi9/ubi-minimal:9.8-1782797275" \
    fetcher_hash="8201445bebcb5bd4fe23fcc2a76cd5fec029ab401d270926a1563c03b36f0137" \
    keycloak_image="quay.io/keycloak/keycloak:26.6.4" \
    keycloak_hash="22c8cf9e79af88d320499c93994bb2c319ca255092d8ae7c7a45dd46d68192e2"

FROM ${fetcher_image}@sha256:${fetcher_hash} as fetcher

ARG GOMPLATE_VERSION \
    WAIT_FOR_VERSION \
    CONTAINER_LIBRARY_VERSION \
    RESTRICT_CLIENT_AUTH_VERSION

    # renovate: datasource=github-releases depName=hairyhenderson/gomplate
ENV GOMPLATE_VERSION="${GOMPLATE_VERSION:-v5.1.0}" \
    # renovate: datasource=github-releases depName=thegeeklab/wait-for
    WAIT_FOR_VERSION="${WAIT_FOR_VERSION:-v0.4.4}" \
    # renovate: datasource=github-releases depName=sventorben/keycloak-restrict-client-auth
    RESTRICT_CLIENT_AUTH_VERSION="${RESTRICT_CLIENT_AUTH_VERSION:-v26.1.0}"

RUN microdnf install -y \
        tar \
        gzip \
        npm; \
    mkdir -p /opt/fetcher/container-library; \
    curl -SsfL -o /opt/fetcher/gomplate "https://github.com/hairyhenderson/gomplate/releases/download/${GOMPLATE_VERSION}/gomplate_linux-amd64"; \
    \
    curl -SsfL -o /opt/fetcher/wait-for "https://github.com/thegeeklab/wait-for/releases/download/${WAIT_FOR_VERSION}/wait-for"; \
    \
    curl -SsfL -o /opt/fetcher/keycloak-restrict-client-auth.jar \
    "https://github.com/sventorben/keycloak-restrict-client-auth/releases/download/${RESTRICT_CLIENT_AUTH_VERSION}/keycloak-restrict-client-auth.jar"; \
    microdnf remove -y tar gzip npm

FROM ${keycloak_image}@sha256:${keycloak_hash} as builder

ARG DB_TYPE
ARG CERT_FILE
ARG CERT_KEY
ARG URL
ARG HTTPS_PORT

# https://www.keycloak.org/server/all-config?options-filter=all
ENV KC_DB="$DB_TYPE" \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_HTTP_RELATIVE_PATH=/auth \
    KC_HOSTNAME_URL="$URL" \
    KC_HTTPS_PORT="$HTTPS_PORT" \
    KC_HTTPS_CERTIFICATE_FILE="$CERT_FILE" \
    KC_HTTPS_CERTIFICATE_KEY_FILE="$CERT_KEY" \
    KC_FIPS_MODE=strict \
    KC_CACHE=ispn \
    KC_CACHE_CONFIG_FILE=cache-ispn-local.xml \
    KC_TRANSACTION_XA_ENABLED=true \
    QUARKUS_TRANSACTION_MANAGER_ENABLE_RECOVERY=true

COPY --from=fetcher --chown=1000 /opt/fetcher/keycloak-restrict-client-auth.jar /opt/keycloak/providers/keycloak-restrict-client-auth.jar
ADD overlay/opt/keycloak/conf/ /opt/keycloak/conf/

RUN \
    # fips needs to be enabled on the host machine running this container
    # el9 based distro's: fips-mode-setup --enable; reboot
    /opt/keycloak/bin/kc.sh build --features=fips --fips-mode=strict

FROM ${keycloak_image}@sha256:${keycloak_hash}

ARG SUBSCRIPTION_USER
ARG SUBSCRIPTION_PASS
ARG DB_TYPE
ARG KEY_FILE
ARG KEY_PASS
ARG URL
ARG HTTPS_PORT

ENV KC_HTTP_RELATIVE_PATH=/auth \
    QUARKUS_TRANSACTION_MANAGER_ENABLE_RECOVERY=true \
    JAVA_HOME="/usr/lib/jvm/jre-17-openjdk"

COPY --from=builder /opt/keycloak/lib/quarkus/ /opt/keycloak/lib/quarkus/
COPY --from=builder /opt/keycloak/providers/ /opt/keycloak/providers/
COPY --from=fetcher /opt/fetcher/gomplate /usr/local/bin/gomplate
COPY --from=fetcher /opt/fetcher/wait-for /usr/local/bin/wait-for
COPY --from=fetcher /keycloak-restrict-client-auth.jar-deps.html /opt/keycloak/providers/
ADD overlay/ /
COPY --chmod=755 certs/ /opt/certs

USER 0
WORKDIR /artifacts
ARG SCAP_PROFILE=xccdf_org.ssgproject.content_profile_stig \
    SCAP_SNAME=STIG \
    BENCHMARK=ssg-rhel9-ds.xml

COPY --chmod=755 el9-container-hardening.sh .

# if building container from rhel host os, with subscription activated, pass following volume mounts to container runtime
# podman run --rm -it \
#  -v "$PWD/entitlement:/run/secrets/etc-pki-entitlement" \
#  -v "$PWD/rhsm:/run/secrets/rhsm" \
#  -v "$PWD/redhat.repo:/run/secrets/redhat.repo" \
#  -d quay.io/keycloak/keycloak:22.0.5
RUN \
    sed -i 's/\(def in_container():\)/\1\n    return False/g' /usr/lib64/python*/*-packages/rhsm/config.py; \
    subscription-manager register --username "${SUBSCRIPTION_USER}" --password "${SUBSCRIPTION_PASS}" --auto-attach; \
    subscription-manager repos --enable codeready-builder-for-rhel-9-$(arch)-rpms; \
    microdnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm; \
    microdnf install -y yum-utils; \
    microdnf update -y; \
    microdnf install -y \
        bash \
        clamav \
        clamav-update \
        java-17-openjdk \
        openscap \
        scap-security-guide \
        wget \
        bzip2; \
    groupadd -g 1001 keycloak; \
    useradd -u 1001 -r -g keycloak keycloak -m; \
    bash -c "./el9-container-hardening.sh"; \
    wget  https://www.redhat.com/security/data/oval/v2/RHEL9/rhel-9.oval.xml.bz2; \
    bzip2 -d rhel-9.oval.xml.bz2; \
    oscap oval eval --report keycloak-rhel9-cve-report.html rhel-9.oval.xml || :; \
    oscap xccdf eval --profile ${SCAP_PROFILE} --results keycloak_rhel9-${SCAP_SNAME}-scap-report.xml \
    --report keycloak_rhel9-${SCAP_SNAME}-scap-report.html /usr/share/xml/scap/ssg/content/${BENCHMARK} || :; \
    freshclam; \
    clamscan -rvi -l AV_scan.log --exclude-dir="^/sys|^/dev" / || :; \
    chown -R keycloak:keycloak /home/keycloak; \
    grep -Hrn FOUND AV_scan.log; \
    microdnf remove -y clamav clamav-update openscap scap-security-guide wget bzip2; \
    microdnf clean all; \
    rm -rf /var/cache/dnf /var/cache/yum /tmp/* /var/tmp/*; \
    truncate -s 0 /var/log/*log

RUN \
    echo "networkaddress.cache.ttl=5" >> "${JAVA_HOME}/conf/security/java.security"; \
    echo "fips.provider.7=XMLDSig" >> "${JAVA_HOME}/conf/security/java.security"; \
    chmod 755 /usr/local/bin/gomplate; \
    chmod 755 /usr/local/bin/wait-for; \
    mkdir -p /opt/keycloak/themes /opt/keycloak/providers /opt/keycloak/dependencies /opt/keycloak/cache; \
    chown -R 1000:root /opt/keycloak/themes /opt/keycloak/providers /opt/keycloak/dependencies /opt/keycloak/cache /opt/keycloak/conf; \
    chmod 755 /opt/keycloak/themes /opt/keycloak/providers /opt/keycloak/dependencies; \
    chmod 700 /opt/keycloak/cache /opt/keycloak/conf

USER 1000
WORKDIR /opt/keycloak
EXPOSE 8080 8443
HEALTHCHECK --timeout=5m --start-period=2m --retries=3 \
   CMD curl -fs http://localhost:8080 || curl -fsk https://localhost:8443 || exit 1
ENTRYPOINT ["/usr/bin/entrypoint"]
