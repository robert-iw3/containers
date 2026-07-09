# syntax=docker/dockerfile:1

ARG repo="quay.io/almalinuxorg" \
    base_image="10-minimal" \
    image_hash="561a7e1d7644dc8e1073ef0d91f6850f7d88761a029e4786afc8befc6bd897e7"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

LABEL \
    org.opencontainers.image.name='Splunk Universal Forwarder' \
    org.opencontainers.image.description='Universal Forwarders provide reliable, secure data collection from remote sources and forward that data into Splunk software for indexing and consolidation.' \
    org.opencontainers.image.usage='https://help.splunk.com/en/splunk-enterprise/forward-and-process-data/universal-forwarder-manual' \
    org.opencontainers.image.url='https://www.splunk.com/' \
    org.opencontainers.image.licenses='https://www.splunk.com/en_us/about-splunk/contact-us.html' \
    org.opencontainers.image.vendor='splunk> | Cisco Systems' \
    org.opencontainers.image.schema-version='10.0.0'

ENV SPLUNK_PRODUCT universalforwarder
ENV SPLUNK_VERSION 10.0.0
ENV SPLUNK_BUILD c486717c322b
ENV SPLUNK_FILENAME splunkforwarder-${SPLUNK_VERSION}-${SPLUNK_BUILD}-linux-amd64.tgz

ENV SPLUNK_HOME /opt/splunk
ENV SPLUNK_GROUP splunk
ENV SPLUNK_USER splunk
ENV SPLUNK_BACKUP_DEFAULT_ETC /var/opt/splunk

RUN \
    microdnf install -y yum-utils epel-release; \
    /usr/bin/crb enable; \
    microdnf update -y; \
    microdnf install -y \
        bash \
        shadow-utils \
        passwd \
        wget \
        tar \
        sudo \
        diffutils \
        procps-ng \
        zlib \
        krb5-libs \
        python3 \
        openssl \
        clamav \
        openscap \
        scap-security-guide \
        clamav-update; \
    \
    groupadd -r ${SPLUNK_GROUP}; \
    useradd --system -s /sbin/nologin -u 333 -g ${SPLUNK_GROUP} ${SPLUNK_USER} -m; \
    passwd -l splunk; \
    \
    mkdir -p ${SPLUNK_HOME}; \
    wget --progress=bar:force -O /tmp/${SPLUNK_FILENAME} https://download.splunk.com/products/${SPLUNK_PRODUCT}/releases/${SPLUNK_VERSION}/linux/${SPLUNK_FILENAME}; \
    wget --progress=bar:force -O /tmp/${SPLUNK_FILENAME}.sha512 https://download.splunk.com/products/${SPLUNK_PRODUCT}/releases/${SPLUNK_VERSION}/linux/${SPLUNK_FILENAME}.sha512; \
    (cd /tmp && sha512sum -c ${SPLUNK_FILENAME}.sha512); \
    tar xzf /tmp/${SPLUNK_FILENAME} --strip 1 -C ${SPLUNK_HOME}; \
    rm /tmp/${SPLUNK_FILENAME}; \
    rm /tmp/${SPLUNK_FILENAME}.sha512; \
    mkdir -p /var/opt/splunk; \
    cp -R ${SPLUNK_HOME}/etc ${SPLUNK_BACKUP_DEFAULT_ETC}; \
    rm -fR ${SPLUNK_HOME}/etc; \
    chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_HOME}; \
    chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_BACKUP_DEFAULT_ETC}

COPY --chmod=755 docker-entrypoint.sh /sbin/entrypoint.sh
#COPY splunkuf-ca.openssl.conf .
#COPY splunkuf_openssl.conf .
#COPY --chmod=755 key-gen.sh .
#RUN bash -c "key-gen.sh"

# Run hardening script and collect build security artifacts, Compliance/CVE/AV
WORKDIR /home/splunk/artifacts

ARG SCAP_PROFILE=xccdf_org.ssgproject.content_profile_stig \
    SCAP_SNAME=STIG \
    BENCHMARK=ssg-almalinux10-ds.xml

COPY --chmod=755 el10-container-hardening.sh .

RUN \
    bash -c "./el10-container-hardening.sh"; \
    wget --progress=bar:force https://security.almalinux.org/oval/org.almalinux.alsa-10.xml; \
    oscap oval eval --report splunk-alma10-cve-report.html org.almalinux.alsa-10.xml || :; \
    oscap ds sds-validate /usr/share/xml/scap/ssg/content/${BENCHMARK} \ && echo "ok" || echo "exit code = $? not ok"; \
    oscap xccdf eval --profile ${SCAP_PROFILE} --results splunk_alma10-${SCAP_SNAME}-scap-report.xml \
    --report splunk_alma10-${SCAP_SNAME}-scap-report.html /usr/share/xml/scap/ssg/content/${BENCHMARK} || :; \
    freshclam; \
    clamscan -rvi -l clamav_scan.log --exclude-dir="^/sys" / || :; \
    chown -R splunk:splunk /home/splunk; \
    grep -Hrn FOUND clamav_scan.log; \
    microdnf remove -y clamav clamav-update openscap scap-security-guide wget bzip2; \
    /usr/bin/crb disable; \
    microdnf remove -y epel-release yum-utils

RUN \
    microdnf clean all; \
    rm -rf /var/cache/dnf /var/cache/yum /tmp/* /var/tmp/*; \
    truncate -s 0 /var/log/*log; \
    echo '%splunk ALL=(splunk) NOPASSWD: /sbin/entrypoint.sh' >> /etc/sudoers; \
    echo '%splunk ALL=(splunk) NOPASSWD: ALL, !/bin/sh, !/bin/bash, !/sbin/nologin, !/bin/bash2, !/bin/ash, !/bin/bsh, !/bin/ksh, !/bin/tcsh, !/bin/csh, !/bin/zsh' >> /etc/sudoers

# Ports Splunk Daemon, Network Input, HTTP Event Collector
EXPOSE 8089/tcp 1514 8088/tcp

WORKDIR /opt/splunk

# Configurations folder, var folder for everything (indexes, logs, kvstore)
VOLUME [ "/opt/splunk/etc", "/opt/splunk/var" ]

USER splunk
ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["start-service"]