FROM docker.io/ubuntu:24.04 AS builder

RUN for iter in 1 2 3 4 5 6 7 8 9 10; do \
      apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl  && \
      exit_code=0 && break || \
        exit_code=$? && echo "apt-get error: retry $iter in 10s" && sleep 10; \
    done; \
    exit $exit_code

    RUN set -eux ; \
        tini_bin="" ; \
        case "$(arch)" in \
            aarch64) tini_bin='tini-arm64' ;; \
            x86_64)  tini_bin='tini-amd64' ;; \
            *) echo >&2 ; echo >&2 "Unsupported architecture $(arch)" ; echo >&2 ; exit 1 ;; \
        esac ; \
        curl --retry 10 -S -L -O https://github.com/krallin/tini/releases/download/v0.19.0/${tini_bin} ; \
        curl --retry 10 -S -L -O https://github.com/krallin/tini/releases/download/v0.19.0/${tini_bin}.sha256sum ; \
        sha256sum -c ${tini_bin}.sha256sum ; \
        rm ${tini_bin}.sha256sum ; \
        mv ${tini_bin} /bin/tini ; \
        chmod 0555 /bin/tini

RUN mkdir /usr/share/elasticsearch
WORKDIR /usr/share/elasticsearch

RUN curl --retry 10 -S -L --output /tmp/elasticsearch.tar.gz https://artifacts-no-kpi.elastic.co/downloads/elasticsearch/elasticsearch-8.17.0-linux-$(arch).tar.gz

RUN tar -zxf /tmp/elasticsearch.tar.gz --strip-components=1

COPY config/elasticsearch.yml config/
COPY config/log4j2.properties config/log4j2.docker.properties

RUN sed -i -e 's/ES_DISTRIBUTION_TYPE=tar/ES_DISTRIBUTION_TYPE=docker/' bin/elasticsearch-env && \
    mkdir data && \
    mv config/log4j2.properties config/log4j2.file.properties && \
    mv config/log4j2.docker.properties config/log4j2.properties && \
    find . -type d -exec chmod 0555 {} + && \
    find . -type f -exec chmod 0444 {} + && \
    chmod 0555 bin/* jdk/bin/* jdk/lib/jspawnhelper modules/x-pack-ml/platform/linux-*/bin/* && \
    chmod 0775 bin config config/jvm.options.d data logs plugins && \
    find config -type f -exec chmod 0664 {} +

FROM ubuntu:24.04

RUN yes no | dpkg-reconfigure dash && \
    for iter in 1 2 3 4 5 6 7 8 9 10; do \
      export DEBIAN_FRONTEND=noninteractive && \
      apt-get update && \
      apt-get upgrade -y && \
      apt-get install -y --no-install-recommends \
        ca-certificates curl netcat p11-kit unzip zip  && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/* && \
      exit_code=0 && break || \
        exit_code=$? && echo "apt-get error: retry $iter in 10s" && sleep 10; \
    done; \
    exit $exit_code

RUN groupadd -g 1000 elasticsearch && \
    adduser --uid 1000 --gid 1000 --home /usr/share/elasticsearch elasticsearch && \
    adduser elasticsearch root && \
    chown -R 0:0 /usr/share/elasticsearch

ENV ELASTIC_CONTAINER true

WORKDIR /usr/share/elasticsearch

COPY --from=builder --chown=0:0 /usr/share/elasticsearch /usr/share/elasticsearch

COPY --from=builder --chown=0:0 /bin/tini /bin/tini

ENV PATH /usr/share/elasticsearch/bin:$PATH
ENV SHELL /bin/bash
COPY bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod g=u /etc/passwd && \
    chmod 0555 /usr/local/bin/docker-entrypoint.sh && \
    find / -xdev -perm -4000 -exec chmod ug-s {} + && \
    chmod 0775 /usr/share/elasticsearch && \
    chown elasticsearch bin config config/jvm.options.d data logs plugins

COPY bin/docker-openjdk /etc/ca-certificates/update.d/docker-openjdk
RUN /etc/ca-certificates/update.d/docker-openjdk

EXPOSE 9200 9300

ENTRYPOINT ["/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["eswrapper"]

USER 1000:0