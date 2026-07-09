# syntax=docker/dockerfile:1.4
FROM docker.io/debian:trixie-20250827-slim AS builder

RUN \
  set -e; \
  apt-get update; \
  apt-get -y install --no-install-recommends \
    curl=8.8.0-1 \
    wget=1.22.0-1 \
    gnupg2=2.2.43-8 \
    ca-certificates=20240203; \
  rm -rf /var/lib/apt/lists/*

ENV GOSU_VERSION=1.17
RUN \
  set -e; \
  ARCH=$(dpkg --print-architecture); \
  wget -nv -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$ARCH"; \
  wget -nv -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$ARCH.asc"; \
  export GNUPGHOME="$(mktemp -d)"; \
  for server in keys.openpgp.org keyserver.ubuntu.com pgp.mit.edu; do \
      gpg --batch --keyserver $server --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && break || : ; \
  done; \
  gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu; \
  rm -rf "$GNUPGHOME" /usr/local/bin/gosu.asc; \
  chmod +x /usr/local/bin/gosu

ENV FLINK_TGZ_URL=https://dlcdn.apache.org/flink/flink-2.3.0/flink-2.3.0-bin-scala_2.12.tgz \
    FLINK_ASC_URL=https://downloads.apache.org/flink/flink-2.3.0/flink-2.3.0-bin-scala_2.12.tgz.asc \
    GPG_KEY=E11F792053638C56C98ACFADB5B638DCA5F94E4A \
    CHECK_GPG=true

RUN \
  set -e; \
  wget -nv -O flink.tgz "$FLINK_TGZ_URL"; \
  if [ "$CHECK_GPG" = "true" ]; then \
    wget -nv -O flink.tgz.asc "$FLINK_ASC_URL"; \
    export GNUPGHOME="$(mktemp -d)"; \
    for server in keys.openpgp.org keyserver.ubuntu.com pgp.mit.edu; do \
        gpg --batch --keyserver $server --recv-keys "$GPG_KEY" && break || : ; \
    done; \
    gpg --batch --verify flink.tgz.asc flink.tgz; \
    rm -rf "$GNUPGHOME" flink.tgz.asc; \
  fi; \
  mkdir -p /opt/flink; \
  tar -xf flink.tgz -C /opt/flink --strip-components=1; \
  rm flink.tgz

FROM docker.io/debian:trixie-20250827-slim

RUN \
  set -e; \
  apt-get update; \
  apt-get -y install --no-install-recommends \
    openjdk-21-jdk=21.0.4+7-2 \
    libnss3=2:3.103-1 \
    libc6=2.40-2 \
    coreutils=9.4-2.1 \
    procps=2:4.0.4-5 \
    python3=3.12.5-1 \
    python3-pip=24.2+dfsg-1 \
    libsnappy1v5=1.2.1-1 \
    gettext-base=0.22.5-1 \
    libjemalloc-dev=5.3.0-2; \
  rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/gosu /usr/local/bin/gosu
COPY --from=builder /opt/flink /opt/flink

RUN groupadd --system --gid=9999 flink && \
    useradd --system --home-dir /opt/flink --uid=9999 --gid=flink flink && \
    chown -R flink:flink /opt/flink

ENV FLINK_HOME=/opt/flink
ENV PATH=$FLINK_HOME/bin:$PATH
WORKDIR $FLINK_HOME
USER flink

RUN \
  CONF_FILE="${FLINK_HOME}/conf/config.yaml"; \
  /bin/bash "$FLINK_HOME/bin/config-parser-utils.sh" "${FLINK_HOME}/conf" "${FLINK_HOME}/bin" "${FLINK_HOME}/lib" \
    "-repKV" "rest.address,localhost,0.0.0.0" \
    "-repKV" "rest.bind-address,localhost,0.0.0.0" \
    "-repKV" "jobmanager.bind-host,localhost,0.0.0.0" \
    "-repKV" "taskmanager.bind-host,localhost,0.0.0.0" \
    "-rmKV" "taskmanager.host=localhost";

COPY docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
EXPOSE 6123 8081
CMD ["standalone-job"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8081 || exit 1