FROM docker.io/debian:trixie

ENV SPLUNK_PRODUCT universalforwarder
ENV SPLUNK_VERSION 10.0.0
ENV SPLUNK_BUILD c486717c322b
ENV SPLUNK_FILENAME splunkforwarder-${SPLUNK_VERSION}-${SPLUNK_BUILD}-linux-amd64.tgz

ENV SPLUNK_HOME /opt/splunk
ENV SPLUNK_GROUP splunk
ENV SPLUNK_USER splunk
ENV SPLUNK_BACKUP_DEFAULT_ETC /var/opt/splunk
ARG DEBIAN_FRONTEND=noninteractive

# add splunk:splunk user
RUN \
    groupadd -r ${SPLUNK_GROUP}; \
    useradd -r -m -g ${SPLUNK_GROUP} ${SPLUNK_USER} -s /sbin/nologin; \
    \
    apt-get update; \
    apt-get install -y locales; \
    rm -rf /var/lib/apt/lists/*; \
	localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

ENV LANG en_US.utf8

# Download official Splunk release, verify checksum and unzip in /opt/splunk
# Also backup etc folder, so it will be later copied to the linked volume
RUN \
    apt-get update; \
    apt-get install -y bash wget sudo procps openssl; \
    mkdir -p ${SPLUNK_HOME}; \
    wget -qO /tmp/${SPLUNK_FILENAME} https://download.splunk.com/products/${SPLUNK_PRODUCT}/releases/${SPLUNK_VERSION}/linux/${SPLUNK_FILENAME}; \
    wget -qO /tmp/${SPLUNK_FILENAME}.sha512 https://download.splunk.com/products/${SPLUNK_PRODUCT}/releases/${SPLUNK_VERSION}/linux/${SPLUNK_FILENAME}.sha512; \
    (cd /tmp && sha512sum -c ${SPLUNK_FILENAME}.sha512); \
    tar xzf /tmp/${SPLUNK_FILENAME} --strip 1 -C ${SPLUNK_HOME}; \
    rm /tmp/${SPLUNK_FILENAME}; \
    rm /tmp/${SPLUNK_FILENAME}.sha512; \
    apt-get purge -y --auto-remove wget; \
    mkdir -p /var/opt/splunk; \
    cp -R ${SPLUNK_HOME}/etc ${SPLUNK_BACKUP_DEFAULT_ETC}; \
    rm -fR ${SPLUNK_HOME}/etc; \
    chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_HOME}; \
    chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_BACKUP_DEFAULT_ETC}; \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=755 entrypoint.sh /sbin/entrypoint.sh
COPY splunkuf-ca.openssl.conf .
COPY splunkuf_openssl.conf .
COPY --chmod=755 key-gen.sh .

RUN bash -c "key-gen.sh"

# Ports Splunk Daemon, Network Input, HTTP Event Collector
EXPOSE 8089/tcp 1514/tcp 8088/tcp

WORKDIR /opt/splunk

# Configurations folder, var folder for everyting (indexes, logs, kvstore)
VOLUME [ "/opt/splunk/etc", "/opt/splunk/var" ]

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["start-service"]
