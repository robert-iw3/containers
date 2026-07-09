#!/bin/sh

# splunk build and runtime library packages


microdnf -y --nodocs install \
    wget \
    sudo \
    shadow-utils \
    procps \
    tar \
    make \
    gcc \
    openssl-devel \
    bzip2-devel \
    libffi-devel \
    findutils \
    libssh-devel \
    libcurl-devel \
    ncurses-devel \
    diffutils \
    unzip \
    bzip2

microdnf -y --nodocs update \
    gnutls \
    kernel-headers \
    libdnf \
    librepo \
    libnghttp2 \
    nettle \
    libpwquality \
    libxml2 \
    systemd-libs \
    lz4-libs \
    curl \
    rpm \
    rpm-libs \
    sqlite-libs \
    cyrus-sasl-lib \
    vim \
    expat \
    openssl-libs \
    xz-libs \
    zlib \
    libsolv \
    file-libs \
    pcre \
    libarchive \
    libgcrypt \
    libksba \
    libstdc++ \
    json-c \
    gnupg

microdnf -y --nodocs reinstall tzdata || microdnf -y --nodocs update tzdata