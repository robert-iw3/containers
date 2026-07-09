FROM docker.io/alpine:3

RUN \
    apk update; \
    apk add --no-cache \
        ca-certificates \
        ruby \
        ruby-irb \
        ruby-etc \
        tini \
        libmaxminddb \
        geoip \
        snappy \
        libssl3 \
        libcrypto3; \

    \
    apk add --no-cache --virtual .build-deps \
        make \
        gcc \
        g++ \
        libc-dev \
        wget \
        bzip2 \
        zlib-dev \
        git \
        linux-headers \
        automake \
        autoconf \
        libtool \
        build-base \
        ruby-dev \
        libc6-compat \
        geoip-dev \
        snappy-dev \
        gnupg \
        bash \
        openssl-dev \
        ruby-bigdecimal; \
    \
    echo 'gem: --no-document' >> /etc/gemrc; \
    gem install fluentd -v 1.18.0; \
    gem install elasticsearch -v 8.18.0 \
    gem install fluent-plugin-elasticsearch -v '~> 5.4.3'; \
    gem install fluent-plugin-cloudwatch -v 2.1.1; \
    gem install fluent-plugin-grok-parser -v 2.6.2; \
    gem install fluent-plugin-s3 -v 1.8.2; \
    gem install specific_install -v 0.3.8; \
    gem install fluent-plugin-label-router -v 0.4.0; \
    gem install fluent-plugin-prometheus -v '~> 2.2' \
    gem install fluent-plugin-record-modifier -v '~> 2.2' \
    gem install fluent-plugin-grafana-loki -v '~> 1.2' \
    gem sources --clear-all \
    \
    apk del --purge --no-network .build-deps; \
    rm -rf /tmp/* /var/tmp/* /usr/lib/ruby/gems/*/cache/*.gem /usr/lib/ruby/gems/3.*/gems/fluentd-*/test; \
    rm -rf /usr/local/bundle/cache/* && find /usr/local/bundle -name '*.o' -delete; \
    \
    addgroup -g 65535 fluent; \
    adduser --shell /sbin/nologin --disabled-password -h /home/fluent --uid 65535 --ingroup fluent fluent; \
    find /usr/local/bundle/gems/ -newer /etc/gemrc -exec chown fluent:fluent {} \; ; \
    mkdir -p /fluentd/log /fluentd/etc /fluentd/plugins; \
    chown -R fluent:fluent /fluentd

COPY fluent.conf /fluentd/etc
COPY --chmod=755 entrypoint.sh /bin
COPY healthy.sh /bin

WORKDIR /home/fluent/

RUN \
    apk add --no-cache clamav freshclam; \
    freshclam; \
    clamscan -r -v -i -l AV_scan.log --exclude-dir="^/sys" / || :; \
    chown fluent:fluent AV_scan.log; \
    grep -Hrn FOUND AV_scan.log; \
    apk del clamav freshclam; \
    rm -rf /var/cache/apk/*; \
    truncate -s 0 /var/log/*log

ENV FLUENTD_CONF="fluent.conf"

ENV LD_PRELOAD=""
EXPOSE 24224 5140

USER fluent
ENTRYPOINT ["tini",  "--", "/bin/entrypoint.sh"]
CMD ["fluentd"]
