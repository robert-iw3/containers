# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL org.opencontainers.image.name='Yara' \
    org.opencontainers.image.description='The pattern matching swiss knife for malware researchers.' \
    org.opencontainers.image.usage='https://yara.readthedocs.io/en/stable/' \
    org.opencontainers.image.url='https://virustotal.github.io/yara/' \
    org.opencontainers.image.licenses='BSD 3-Clause "New" or "Revised" License' \
    org.opencontainers.image.vendor='VirusTotal' \
    org.opencontainers.image.schema-version='4.5.5' \
    MAINTAINER="@rw"

ENV VER 4.5.5

RUN \
    apk add --no-cache \
        bash \
        git \
        openssl \
        file \
        jansson \
        libmagic \
        bison \
        su-exec \
        python3 \
        py3-pip; \
	\
    apk add --no-cache -t .yara-deps \
        gcc \
        g++ \
        musl-dev \
        linux-headers \
        python3-dev \
        openssl-dev \
        jansson-dev \
        build-base \
        npm \
        libc-dev \
        file-dev \
        automake \
        autoconf \
        libtool \
        flex; \
    cd /tmp; \
    git clone --recursive --branch v${VER} https://github.com/VirusTotal/yara.git; \
    cd yara; \
    \
    ./bootstrap.sh; \
    sync; \
    ./configure \
        --with-crypto \
        --enable-magic \
        --enable-cuckoo \
        --enable-dotnet; \
    make; \
    make install; \
    \
    git clone --recursive https://github.com/VirusTotal/yara-python; \
    cd yara-python; \
    python3 setup.py build --dynamic-linking; \
    python3 setup.py install; \
    \
    mkdir /rules; \
    rm -rf /tmp/*; \
    cd /; \
    apk del --purge --no-network .yara-deps; \
    \
    addgroup -g 65535 yara; \
    adduser --disabled-password \
    -h /home/yara --uid 65535 --ingroup yara yara

COPY --chown=yara:yara /rules /rules
COPY --chown=yara:yara malware.yar /rules
COPY --chown=yara:yara include_rules.yar /rules
COPY --chown=yara:yara /iocs /iocs

WORKDIR /rules
#RUN python3 build-rules.py
VOLUME /malware
VOLUME /rules
WORKDIR /malware
USER yara
