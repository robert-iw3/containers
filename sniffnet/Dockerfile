FROM docker.io/debian:13

RUN \
    apt-get -qq update ; \
    apt-get -yq upgrade ; \
    apt-get install -yq \
        curl \
        sudo \
        libmagic-dev \
        wget \
        libfreetype6 \
        libexpat1 \
        libpcap0.8 \
        libasound2 \
        libfontconfig1 \
        libgtk-3-0 \
        libcap2-bin \
        logrotate \
        libpcap-dev \
        libasound2-dev \
        libfontconfig1-dev \
        libgtk-3-dev \
        libxkbcommon-x11-0 \
    ; \
    wget --progress=bar:force https://github.com/GyulyVGC/sniffnet/releases/latest/download/Sniffnet_LinuxDEB_amd64.deb ; \
    dpkg -i Sniffnet_LinuxDEB_amd64.deb ; \
    rm -f Sniffnet_LinuxDEB_amd64.deb ; \
    apt-get -yq autoremove ; \
    apt-get -yq clean ; \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* ; \
    setcap cap_net_raw,cap_net_admin=eip /usr/bin/sniffnet

ENTRYPOINT ["sniffnet"]