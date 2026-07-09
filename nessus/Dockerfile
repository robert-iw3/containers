# syntax=docker/dockerfile:1
# Nessus: The Global Gold Standard in Vulnerability Assessment
# Base image: oraclelinux:9-slim-fips (FIPS-compliant)
# https://www.tenable.com/products/nessus
ARG repo="docker.io" \
    base_image="oraclelinux:9-slim-fips" \
    image_hash="d0263f0c735047b6977c65fb289195dde2857241cd690b8d52c9edfcb514b4ae" \
    VERSION="10.8.4"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

LABEL org.opencontainers.image.name='Nessus' \
    org.opencontainers.image.description='Vulnerability Assessment for Modern Attack Surfaces' \
    org.opencontainers.image.usage='https://docs.tenable.com/Nessus.htm' \
    org.opencontainers.image.url='https://www.tenable.com/products/nessus' \
    org.opencontainers.image.licenses='Tenable' \
    org.opencontainers.image.vendor='Tenable' \
    org.opencontainers.image.schema-version='10.8.4' \
    MAINTAINER="@rw"

RUN microdnf install -y epel-release ; \
    microdnf update -y ; \
    microdnf install -y java-21-openjdk curl ; \
    microdnf clean all

FROM base AS download

ARG VERSION
RUN curl --retry 3 --request GET \
    --url "https://www.tenable.com/downloads/api/v2/pages/nessus/files/Nessus-${VERSION}-el9.x86_64.rpm" \
    --output "Nessus-${VERSION}-el9.x86_64.rpm" ; \
    rpm -ivh Nessus-${VERSION}-el9.x86_64.rpm

FROM base

COPY --from=download /opt/nessus /opt/nessus

ARG CA_LIFE=730
ARG CERT_LIFE=365
ARG COUNTRY=US
ARG STATE=XX
ARG CITY=XXXX
ARG ORG=Testing
ARG HOSTNAME=nessus.testing.io

RUN microdnf install -y \
        clamav clamav-update openscap scap-security-guide wget bzip2 ; \
    echo "${HOSTNAME}" > /etc/hostname ; \
    groupadd -r nessus ; \
    useradd -r -g nessus nessus -m -d /home/nessus ; \
    echo -ne "${CA_LIFE}\n${CERT_LIFE}\n${COUNTRY}\n${STATE}\n${CITY}\n${ORG}\n${HOSTNAME}\ny" | /opt/nessus/sbin/nessuscli mkcert ; \
    /opt/nessus/sbin/nessuscli fix --secure ; \
    chown -R nessus:nessus /opt/nessus /home/nessus ; \
    chmod 750 /opt/nessus/sbin/* ; \
    mkdir -p /home/nessus/artifacts /home/nessus/plugins ; \
    chown -R nessus:nessus /home/nessus/artifacts /home/nessus/plugins

WORKDIR /home/nessus/artifacts
ARG SCAP_PROFILE=xccdf_org.ssgproject.content_profile_stig
ARG SCAP_SNAME=STIG
ARG BENCHMARK=ssg-ol9-ds.xml

COPY el9-container-hardening.sh .
RUN chmod +x ./el9-container-hardening.sh ; \
    ./el9-container-hardening.sh ; \
    wget --tries=3 https://linux.oracle.com/security/oval/com.oracle.elsa-ol9.xml.bz2 ; \
    bzip2 -d com.oracle.elsa-ol9.xml.bz2 ; \
    oscap oval eval --report nessus-ol9-cve-report.html com.oracle.elsa-ol9.xml || true ; \
    oscap xccdf eval --profile ${SCAP_PROFILE} --results nessus-ol9-${SCAP_SNAME}-scap-report.xml \
        --report nessus-ol9-${SCAP_SNAME}-scap-report.html /usr/share/xml/scap/ssg/content/${BENCHMARK} || true ; \
    freshclam ; \
    clamscan -rvi -l clamav_scan.log --exclude-dir="^/sys|^/dev" / || true ; \
    grep -Hrn FOUND clamav_scan.log || true ; \
    microdnf remove -y clamav clamav-update openscap scap-security-guide wget bzip2 epel-release ; \
    microdnf clean all ; \
    rm -rf /var/cache/dnf /tmp/* /var/tmp/* ; \
    truncate -s 0 /var/log/*log ; \
    setcap "cap_net_admin,cap_net_raw,cap_sys_resource+eip" /opt/nessus/sbin/nessusd ; \
    setcap "cap_net_admin,cap_net_raw,cap_sys_resource+eip" /opt/nessus/sbin/nessus-service

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f -k https://localhost:8834 || exit 1

WORKDIR /home/nessus
USER nessus
STOPSIGNAL SIGINT
COPY entrypoint.sh /home/nessus/entrypoint.sh
RUN chmod +x /home/nessus/entrypoint.sh
ENTRYPOINT ["/home/nessus/entrypoint.sh"]