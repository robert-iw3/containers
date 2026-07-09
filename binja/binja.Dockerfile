ARG DEBIAN_VERSION=13
FROM docker.io/debian:${DEBIAN_VERSION}

LABEL \
    org.opencontainers.image.name='Binary Ninja' \
    org.opencontainers.image.description='Binary Ninja is an interactive decompiler, disassembler, debugger, \
                                          and binary analysis platform built by reverse engineers, for reverse engineers.'

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    QT_QPA_PLATFORM=xcb \
    QT_QPA_PLATFORM_PLUGIN_PATH=/binja/binaryninja

RUN \
    groupadd -g 1001 binja; \
    useradd -u 1001 -g 1001 -m -s /bin/bash binja; \
    apt-get update ; \
    apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      coreutils \
      locales \
      libxcb-cursor0 \
      libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xkb1 libxkbcommon-x11-0 \
      libstdc++6 \
      libglib2.0-0 \
      libgtk-3-0 \
      libnss3 \
      libx11-6 \
      libxcb1 \
      libxcb-cursor0 \
      libxcb-xinerama0 \
      libxcb-keysyms1 \
      libxcb-randr0 \
      libxcb-image0 \
      libxcb-shm0 \
      libxcb-icccm4 \
      libxcb-sync1 \
      libxcb-xfixes0 \
      libxkbcommon0 \
      libfontconfig1 \
      libglu1-mesa \
      libegl1 \
      libgl1-mesa-glx \
      libdbus-1-3 \
      libexpat1 \
      libuuid1 \
      liblzma5 \
      liblz4-1 \
      libgcrypt20 \
      libgpg-error0 \
      python3 libpython3-all-dev \
      fontconfig \
      unzip \
      wget; \
    \
    locale-gen en_US.UTF-8 ; \
    update-locale LANG=en_US.UTF-8 ; \
    rm -rf /var/lib/apt/lists/* ; \
    \
    mkdir -p /binja/data ; \
    cd /binja ; \
    wget --progress=bar:force https://cdn.binary.ninja/installers/binaryninja_free_linux.zip -O /binja/binja.zip ; \
    unzip binja.zip ; \
    chmod +x /binja/binaryninja ; \
    chown -R binja:binja /binja ; \
    rm -f /binja/binja.zip

WORKDIR /binja/binaryninja
COPY plugins/ plugins/
#USER binja
CMD ["./binaryninja"]
