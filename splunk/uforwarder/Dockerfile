FROM registry.access.redhat.com/ubi9/ubi-minimal as splunk_base

ENV BUSYBOX_URL=https://busybox.net/downloads/busybox-1.36.1.tar.bz2 \
    PYTHON_VERSION=3.9.19 \
    PYTHON_GPG_KEY_ID=E3FF2839C048B25C084DEBE9B26995E310250568

RUN \
    set -e; \
    export LANG=en_US.utf8; \
    \
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
        bzip2; \
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
        gnupg; \
    microdnf -y --nodocs reinstall tzdata || microdnf -y --nodocs update tzdata; \
    \
    cd ~; \
    wget --progress=bar:force -O busybox.tar.bz2 \
        ${BUSYBOX_URL}; \
    bzip2 -d busybox.tar.bz2; \
    tar xf busybox.tar; \
    cd busybox-1.36.1; \
    make defconfig; \
    make; \
    cp busybox /bin/busybox; \
    cd ~; \
    rm -rf busybox.tar busybox-1.36.1/; \
    \
    PY_SHORT=${PYTHON_VERSION%.*}; \
    wget --progress=bar:force -O /tmp/python.tgz \
        https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz; \
    wget --progress=bar:force -O /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc \
        https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz.asc; \
    gpg --keyserver keys.openpgp.org --recv-keys $PYTHON_GPG_KEY_ID \
        || gpg --keyserver pool.sks-keyservers.net --recv-keys $PYTHON_GPG_KEY_ID \
        || gpg --keyserver pgp.mit.edu --recv-keys $PYTHON_GPG_KEY_ID \
        || gpg --keyserver keyserver.pgp.com --recv-keys $PYTHON_GPG_KEY_ID; \
    gpg --verify /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc /tmp/python.tgz; \
    rm /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc; \
    mkdir -p /tmp/pyinstall; \
    tar -xzC /tmp/pyinstall/ --strip-components=1 -f /tmp/python.tgz; \
    rm /tmp/python.tgz; \
    cd /tmp/pyinstall; \
    ./configure \
        --enable-optimizations \
        --prefix=/usr \
        --with-ensurepip=install; \
    make altinstall LDFLAGS="-Wl,--strip-all"; \
    rm -rf /tmp/pyinstall; \
    ln -sf /usr/bin/python${PY_SHORT} /usr/bin/python; \
    ln -sf /usr/bin/pip${PY_SHORT} /usr/bin/pip; \
    ln -sf /usr/bin/python${PY_SHORT} /usr/bin/python3; \
    ln -sf /usr/bin/pip${PY_SHORT} /usr/bin/pip3; \
    \
    cd /; \
    /usr/bin/python3.9 -m pip install --upgrade pip; \
    pip -q --no-cache-dir install --upgrade \
        requests_unixsocket \
        requests \
        six \
        wheel \
        Mako \
        "urllib3<2.0.0" \
        certifi \
        jmespath \
        future \
        avro \
        cryptography \
        lxml \
        protobuf \
        setuptools \
        ansible; \
    \
    find /usr/lib/ -depth \( -type d -a -not -wholename '*/ansible/plugins/test' -a \( -name test -o -name tests -o -name idle_test \) \) -exec rm -rf '{}' \; ; \
    find /usr/lib/ -depth \( -type f -a -name '*.pyc' -o -name '*.pyo' -o -name '*.a' \) -exec rm -rf '{}' \; ; \
    find /usr/lib/ -depth \( -type f -a -name 'wininst-*.exe' \) -exec rm -rf '{}' \; ; \
    ldconfig; \
    \
    microdnf remove -y \
        make \
        gcc \
        openssl-devel \
        bzip2-devel \
        findutils \
        glibc-devel \
        cpp \
        binutils \
        keyutils-libs-devel \
        krb5-devel \
        libcom_err-devel \
        libffi-devel \
        libcurl-devel \
        libselinux-devel \
        libsepol-devel \
        libssh-devel \
        libverto-devel \
        libxcrypt-devel \
        ncurses-devel \
        pcre2-devel \
        zlib-devel \
        diffutils \
        bzip2; \
    microdnf clean all; \
    \
    cd /bin; \
    BBOX_LINKS=( clear find diff hostname killall netstat nslookup ping ping6 readline route syslogd tail traceroute vi ); \
    for item in "${BBOX_LINKS[@]}"; do \
    ln -s busybox $item || true; \
    done; \
    chmod u+s /bin/ping; \
    groupadd sudo; \
    echo " \
    ## Allows people in group sudo to run all commands \
    %sudo  ALL=(ALL)       ALL" >> /etc/sudoers; \
    \
    microdnf clean all; \
    rm -rf /anaconda-post.log /var/log/anaconda/*

FROM splunk_base as package

#
# Download and unpack Splunk Universal Forwarder
#
ARG SPLUNK_BUILD_URL
ENV SPLUNK_HOME=/opt/splunkforwarder

RUN \
    echo "Downloading Splunk and validating the checksum at: ${SPLUNK_BUILD_URL}"; \
    wget -qO /tmp/`basename ${SPLUNK_BUILD_URL}` ${SPLUNK_BUILD_URL}; \
    wget -qO /tmp/splunk.tgz.sha512 ${SPLUNK_BUILD_URL}.sha512; \
    cd /tmp; \
    echo "$(cat /tmp/splunk.tgz.sha512)" | sha512sum --check  --status; \
    rm /tmp/splunk.tgz.sha512; \
    tar -C /opt -zxf /tmp/`basename ${SPLUNK_BUILD_URL}`; \
    mv ${SPLUNK_HOME}/etc ${SPLUNK_HOME}-etc; \
    mkdir -p ${SPLUNK_HOME}/etc ${SPLUNK_HOME}/var

COPY common-files/apps ${SPLUNK_HOME}-etc/apps/

FROM splunk_base as final

ARG UID=41812
ARG GID=41812

ENV SPLUNK_HOME=/opt/splunkforwarder \
    SPLUNK_GROUP=splunk \
    SPLUNK_USER=splunk

COPY common-files/updateetc.sh /sbin

RUN groupadd -r -g ${GID} ${SPLUNK_GROUP}; \
    useradd -r -m -u ${UID} -g ${GID} -s /bin/bash ${SPLUNK_USER}; \
    chmod 755 /sbin/updateetc.sh

COPY --from=package --chown=splunk:splunk /opt /opt

FROM final

ARG SPLUNK_DEFAULTS_URL

ENV SPLUNK_ROLE=splunk_universal_forwarder \
    SPLUNK_DEFAULTS_URL=${SPLUNK_DEFAULTS_URL} \
    SPLUNK_ANSIBLE_HOME=/opt/ansible \
    SPLUNK_OPT=/opt \
    ANSIBLE_USER=ansible \
    ANSIBLE_GROUP=ansible \
    CONTAINER_ARTIFACT_DIR=/opt/container_artifact

COPY common-files/entrypoint.sh /sbin
COPY common-files/checkstate.sh /sbin
COPY common-files/createdefaults.py /sbin

USER root

RUN \
    mkdir -p ${SPLUNK_ANSIBLE_HOME}; \
    wget --progress=bar:force -O splunk-playbooks.zip \
        https://github.com/splunk/splunk-ansible/archive/refs/heads/develop.zip; \
    unzip splunk-playbooks.zip -d ${SPLUNK_ANSIBLE_HOME}; \
    mv ${SPLUNK_ANSIBLE_HOME}/splunk-ansible-develop/* ${SPLUNK_ANSIBLE_HOME}; \
    sed -i -e 's/%sudo\s\+ALL=(ALL\(:ALL\)\?)\s\+ALL/%sudo ALL=NOPASSWD:ALL\nansible ALL=(splunk)NOPASSWD:ALL/g' /etc/sudoers; \
    microdnf install systemd; \
    groupadd -r ${ANSIBLE_GROUP}; \
    useradd -r -m -g ${ANSIBLE_GROUP} -s /bin/bash ${ANSIBLE_USER}; \
    usermod -aG sudo ${ANSIBLE_USER}; \
    usermod -aG ${ANSIBLE_GROUP} ${SPLUNK_USER}; \
    mkdir ${CONTAINER_ARTIFACT_DIR}; \
    chown -R ${ANSIBLE_USER}:${ANSIBLE_GROUP} ${CONTAINER_ARTIFACT_DIR}; \
    chmod -R 775 ${CONTAINER_ARTIFACT_DIR}; \
    chmod -R 555 ${SPLUNK_ANSIBLE_HOME}; \
    chgrp ${ANSIBLE_GROUP} ${SPLUNK_ANSIBLE_HOME} ${SPLUNK_ANSIBLE_HOME}/ansible.cfg; \
    chmod 775 ${SPLUNK_ANSIBLE_HOME}; \
    chmod 664 ${SPLUNK_ANSIBLE_HOME}/ansible.cfg; \
    sed -i '/^\[defaults\]/a\interpreter_python = /usr/bin/python3' ${SPLUNK_ANSIBLE_HOME}/ansible.cfg; \
    chmod 755 /sbin/entrypoint.sh /sbin/createdefaults.py /sbin/checkstate.sh

USER ${SPLUNK_USER}
WORKDIR ${SPLUNK_HOME}
EXPOSE 8089 8088 9997
VOLUME [ "/opt/splunkforwarder/etc", "/opt/splunkforwarder/var" ]
HEALTHCHECK --interval=30s --timeout=30s --start-period=3m --retries=5 CMD /sbin/checkstate.sh || exit 1
ENTRYPOINT [ "/sbin/entrypoint.sh" ]
CMD [ "start-service" ]
