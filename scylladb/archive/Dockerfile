# --format docker
FROM docker.io/debian:13

ARG DOWNLOADS_URL="downloads.bitnami.com/files/stacksmith"

ENV HOME="/" \
    OS_ARCH="${TARGETARCH:-amd64}" \
    OS_FLAVOUR="debian-12" \
    OS_NAME="linux"

RUN \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        libjemalloc-dev \
        libatomic1 \
        libblkid1 \
        libbz2-1.0 \
        libcap2 \
        libcom-err2 \
        libcrypt1 \
        libffi8 \
        libgcc-s1 \
        libgcrypt20 \
        libgmp10 \
        libgnutls30 \
        libgpg-error0 \
        libgssapi-krb5-2 \
        libhogweed6 \
        libidn2-0 \
        libjsoncpp25 \
        libk5crypto3 \
        libkeyutils1 \
        libkrb5-3 \
        libkrb5support0 \
        liblz4-1 \
        liblzma5 \
        libmount1 \
        libmpfr6 \
        libncursesw6 \
        libnettle8 \
        libnsl2 \
        libp11-kit0 \
        libpcre2-8-0 \
        libreadline8 \
        libselinux1 \
        libsmartcols1 \
        libsqlite3-0 \
        libssl3 \
        libstdc++6 \
        libsystemd0 \
        libtasn1-6 \
        libtinfo6 \
        libtirpc3 \
        libudev1 \
        libunistring2 \
        libxxhash0 \
        libzstd1 \
        procps \
        rsyslog \
        zlib1g

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

RUN \
    mkdir -p /tmp/ ; cd /tmp/ || exit 1 ; \
    COMPONENTS=( \
      "python-3.12.11-3-linux-${OS_ARCH}-debian-12" \
      "jre-11.0.27-9-0-linux-${OS_ARCH}-debian-12" \
      "scylladb-2025.1.3-1-linux-${OS_ARCH}-debian-12" \
    ) ; \
    for COMPONENT in "${COMPONENTS[@]}"; do \
      if [ ! -f "${COMPONENT}.tar.gz" ]; then \
        curl -SsLf "https://${DOWNLOADS_URL}/${COMPONENT}.tar.gz" -O ; \
        curl -SsLf "https://${DOWNLOADS_URL}/${COMPONENT}.tar.gz.sha256" -O ; \
      fi ; \
      sha256sum -c "${COMPONENT}.tar.gz.sha256" ; \
      tar -zxf "${COMPONENT}.tar.gz" -C /opt/ --strip-components=2 --no-same-owner ; \
      rm -rf "${COMPONENT}".tar.gz{,.sha256} ; \
    done

RUN \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives; \
    chmod g+rwX /opt; \
    find / -perm /6000 -type f -exec chmod a-s {} \; || true ; \
    apt-get remove -y curl; \
    apt-get autoremove -y

COPY --chmod=755 scripts/ /opt/scripts
COPY --chmod=755 scripts/cassandra-env.sh /opt/scylladb/etc
RUN bash -c "/opt/scripts/scylladb/postunpack.sh"
RUN bash -c "/opt/scripts/java/postunpack.sh"

ENV APP_VERSION="2025.1.3" \
    _APP_NAME="scylladb" \
    JAVA_HOME="/opt/java" \
    PATH="/opt/python/bin:/opt/java/bin:/opt/scylladb/bin:/opt/scylladb/python3/bin:/opt/scylladb/sbin:/opt/scylladb/share/cassandra/bin:/opt/supervisor/bin:$PATH"

USER 1001
ENTRYPOINT [ "/opt/scripts/entrypoint.sh" ]
CMD [ "/opt/scripts/run.sh" ]