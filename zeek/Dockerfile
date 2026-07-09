# syntax=docker/dockerfile:1
# zeek: A powerful network analysis framework.

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS build-env

ARG ZEEK_VERSION=8.0.9
ARG BUILD_PROCS=4

RUN \
    apk add --no-cache \
        zlib \
        openssl \
        libstdc++ \
        libpcap \
        libgcc; \
    apk add --no-cache -t .build-deps \
        bsd-compat-headers \
        libmaxminddb-dev \
        linux-headers \
        openssl-dev \
        libpcap-dev \
        python3-dev \
        zlib-dev \
        flex-dev \
        binutils \
        fts-dev \
        cmake \
        bison \
        bash \
        swig \
        perl \
        make \
        flex \
        git \
        gcc \
        g++ \
        fts \
        krb5-dev; \
    \
    cd /tmp; \
    git clone --recursive --branch v${ZEEK_VERSION} https://github.com/zeek/zeek.git; \
    cd /tmp/zeek; \
    \
    CC=gcc ./configure --prefix=/usr/local/zeek \
    --build-type=Release \
    --disable-broker-tests \
    --disable-auxtools \
    --disable-javascript; \
    \
    make -j ${BUILD_PROCS}; \
    make install; \
    \
    strip -s /usr/local/zeek/bin/zeek; \
    apk del --no-network --purge .build-deps; \
    rm -rf /var/cache/apk/*

FROM ${repo}/${base_image} AS clamav
RUN apk add --no-cache clamav freshclam && \
    freshclam && \
    clamscan -rvi -l /home/zeek/last_scan.log --exclude-dir="^/sys|^/dev" /

FROM ${base_image}

LABEL org.opencontainers.image.name='Zeek' \
    org.opencontainers.image.description='Zeek (formerly Bro) is the worlds leading platform for network security monitoring.' \
    org.opencontainers.image.usage='https://docs.zeek.org/en/master/' \
    org.opencontainers.image.url='https://zeek.org/' \
    org.opencontainers.image.licenses='The Regents of the University of California' \
    org.opencontainers.image.vendor='The Zeek Project' \
    org.opencontainers.image.schema-version='8.0.4' \
    MAINTAINER="@rw"

RUN \
    apk --no-cache add \
        ca-certificates \
        bash \
        zlib \
        openssl \
        libstdc++ \
        libpcap \
        libmaxminddb \
        libgcc \
        fts \
        git \
        python3 \
        py3-pip \
        py3-semantic-version \
        py3-gitpython \
        py3-websockets \
        krb5-libs \
        ethtool \
        util-linux \
        wget && \
    pip install --no-cache-dir prometheus_client

COPY --from=build-env /usr/local/zeek /usr/local/zeek
COPY --from=clamav /home/zeek/last_scan.log /home/zeek/
COPY --chmod=755 entrypoint.sh .
COPY --chmod=755 zeek_exporter.py /usr/local/zeek/bin/zeek_exporter.py

ENV ZEEKPATH=".:/data/config:/usr/local/zeek/share/zeek:/usr/local/zeek/share/zeek/policy:/usr/local/zeek/share/zeek/site" \
    PATH="/usr/local/zeek/bin:${PATH}" \
    PYTHONPATH="/usr/local/zeek/lib/zeek/python:${PYTHONPATH}" \
    ZEEK_DEFAULT_PACKAGES="bro-interface-setup \
        bro-doctor \
        ja3 \
        hassh \
        bzar \
        dovehawk \
        icsnpp-bacnet \
        icsnpp-modbus"

RUN \
    ln -s $(which ethtool) /sbin/ethtool; \
    \
    python3 -m venv zkg; \
    . zkg/bin/activate; \
    python3 -m pip install --upgrade pip; \
    python3 -m pip install --upgrade zkg; \
    zkg autoconfig; \
    zkg refresh; \
    zkg install --force $ZEEK_DEFAULT_PACKAGES; \
    \
    echo "*/5 * * * * /usr/local/zeek/bin/zeekctl cron >> /usr/local/zeek/logs/cron.log 2>&1" >> /etc/crontabs/root; \
    \
    chmod 750 /usr/local/zeek/logs /usr/local/zeek/spool; \
    rm -f /usr/local/zeek/etc/node.cfg

COPY etc/node.cfg /usr/local/zeek/etc/node.cfg
COPY etc/networks.cfg /usr/local/zeek/etc/networks.cfg
COPY etc/zeekctl.cfg /usr/local/zeek/etc/zeekctl.cfg
COPY local.zeek /usr/local/zeek/share/zeek/site/local.zeek
COPY share/zeek/site/ /usr/local/zeek/share/zeek/site/
COPY share/login.zeek /usr/local/zeek/share/zeek/site/login.zeek
COPY share/guess.zeek /usr/local/zeek/share/zeek/site/guess.zeek
COPY share/known-routers.zeek /usr/local/zeek/share/zeek/site/known-routers.zeek
COPY share/guess_ics_map.txt /usr/local/zeek/share/zeek/site/guess_ics_map.txt
ENTRYPOINT ["/entrypoint.sh"]