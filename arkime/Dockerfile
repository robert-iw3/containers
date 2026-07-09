ARG DEBIAN_VERSION=13
FROM docker.io/debian:${DEBIAN_VERSION}

ARG ARKIME_VERSION=6.5.0
ARG ARKIME_DEB_PACKAGE="arkime_${ARKIME_VERSION}-1.debian13_amd64.deb"

ENV ARKIME_VERSION=$ARKIME_VERSION
ENV OS_HOST="os01"
ENV OS_PORT="9200"
ENV OS_USER="admin"
ENV OS_PASSWORD="password1234!!**"
ENV ARKIME_INTERFACE="wlo1"
ENV ARKIME_ADMIN_PASSWORD="admin"
ENV ARKIME_HOSTNAME="localhost"
ENV ARKIMEDIR="/opt/arkime"
ENV CAPTURE="off"
ENV VIEWER="on"
ENV SURICATA="off"
ENV PROXY="off"
ENV WISE="off"

RUN \
    apt-get -qq update ; \
    apt-get -yq upgrade ; \
    apt-get install -yq \
        curl \
        libmagic-dev \
        wget \
        logrotate ; \
    mkdir -p /data ; \
    cd /data ; \
    curl -L -O "https://github.com/arkime/arkime/releases/download/v${ARKIME_VERSION}/${ARKIME_DEB_PACKAGE}" ; \
    dpkg -i "${ARKIME_DEB_PACKAGE}" || true ; \
    apt-get install -yqf ; \
    mv "${ARKIMEDIR}/etc" /data/config ; \
    ln -s /data/config "${ARKIMEDIR}/etc" ; \
    ln -s /data/logs "${ARKIMEDIR}/logs" ; \
    ln -s /data/pcap "${ARKIMEDIR}/raw" ; \
    "${ARKIMEDIR}/bin/arkime_update_geo.sh" ; \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/* ; \
    rm "/data/${ARKIME_DEB_PACKAGE}"

COPY --chmod=755 /scripts /data/
ADD etc/wise.ini ${ARKIMEDIR}/etc/wise.ini

VOLUME ["/data/pcap", "/data/config", "/data/logs"]
EXPOSE 8005
WORKDIR "$ARKIMEDIR"

ENTRYPOINT ["/data/startarkime.sh"]
