FROM quay.io/almalinuxorg/almalinux:10 AS build-env

ARG ELASTIC_VERSION=9.4.3

RUN set -eux ; \
    dnf -y update; \
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

RUN \
    curl --retry 10 -S -L --output /tmp/elasticsearch.tar.gz \
    https://artifacts-no-kpi.elastic.co/downloads/elasticsearch/elasticsearch-${ELASTIC_VERSION}-linux-$(arch).tar.gz; \
    tar -zxf /tmp/elasticsearch.tar.gz --strip-components=1

# https://snyk.io/login?cta=sign-up&loc=nav&page=support_docs_page
# To authenticate using your API token:
#Go to your Snyk account (Account Settings > API Token section).
#In the KEY field, click click to show; then select and copy your API token. A screenshot follows.
#In the CLI, run snyk auth [<API_TOKEN>] or snyk config set api=<token>. The <API_TOKEN>is validated by the Snyk API.
#ENV SNYK_API=

#run SCA scan against source code
#WORKDIR /tmp
#RUN set -x; \
#    dnf install -y npm; \
#    wget https://github.com/elastic/elasticsearch/archive/refs/tags/v${ELASTIC_VERSION}.tar.gz; \
#    tar zxvf v${ELASTIC_VERSION}.tar.gz; cd elasticsearch-${ELASTIC_VERSION}; \
#    npm install -g snyk; \
#    npm install snyk-to-html -g; \
#    snyk config set api=${SNYK_API}; \
#    snyk code test --json | snyk-to-html -o /elasticsearch-code-review.html; \
#    snyk test --json | snyk-to-html -o /elasticsearch-deps.html; \
#    snyk monitor; \
#    npm uninstall -g snyk; \
#    npm uninstall -g snyk-to-html; \
#    dnf remove -y npm

RUN rm -rf /tmp/*

COPY config/elasticsearch.yml config/
COPY config/log4j2.properties config/log4j2.docker.properties

RUN set -eux; \
    sed -i -e 's/ES_DISTRIBUTION_TYPE=tar/ES_DISTRIBUTION_TYPE=docker/' bin/elasticsearch-env; \
    mkdir data; \
    mv config/log4j2.properties config/log4j2.file.properties; \
    mv config/log4j2.docker.properties config/log4j2.properties; \
    find . -type d -exec chmod 0555 {} + ; \
    find . -type f -exec chmod 0444 {} + ; \
    chmod 0555 bin/* jdk/bin/* jdk/lib/jspawnhelper modules/x-pack-ml/platform/linux-*/bin/*; \
    chmod 0775 bin config config/jvm.options.d data logs plugins; \
    find config -type f -exec chmod 0664 {} +

FROM quay.io/almalinuxorg/10-minimal:latest

RUN \
    microdnf install -y yum-utils epel-release; \
    dnf config-manager --set-enabled crb; \
    /usr/bin/crb enable; \
    microdnf update -y; \
    microdnf install -y \
        bash \
        ca-certificates \
        curl \
        netcat \
        p11-kit \
        unzip \
        zip \
        clamav \
        clamav-update \
        openscap \
        scap-security-guide \
        wget \
        bzip2; \
    adduser --uid 1000 --gid 0 --home-dir /usr/share/elasticsearch elasticsearch; \
    chown -R 1000:0 /usr/share/elasticsearch

ENV ELASTIC_CONTAINER true

WORKDIR /usr/share/elasticsearch

COPY --from=build-env --chown=1000:0 /usr/share/elasticsearch /usr/share/elasticsearch
COPY --from=build-env --chown=1000:0 /bin/tini /bin/tini

ENV PATH /usr/share/elasticsearch/bin:$PATH

COPY --chmod=755 bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN set -eux; \
    chmod g=u /etc/passwd; \
    chmod 0555 /usr/local/bin/docker-entrypoint.sh; \
    find / -xdev -perm -4000 -exec chmod ug-s {} + ; \
    chmod 0775 /usr/share/elasticsearch; \
    chown elasticsearch bin config config/jvm.options.d data logs plugins

COPY bin/docker-openjdk /etc/ca-certificates/update.d/docker-openjdk
RUN chmod +x /etc/ca-certificates/update.d/docker-openjdk && /etc/ca-certificates/update.d/docker-openjdk

WORKDIR /usr/share/elasticsearch/artifacts

ARG SCAP_PROFILE=xccdf_org.ssgproject.content_profile_stig \
    SCAP_SNAME=STIG \
    BENCHMARK=ssg-almalinux9-ds.xml

COPY --chmod=755 el9-container-hardening.sh .
#COPY --chown=elasticsearch:elasticsearch --from=build-env /elasticsearch-code-review.html /usr/share/elasticsearch/artifacts
#COPY --chown=elasticsearch:elasticsearch --from=build-env /elasticsearch-deps.html /usr/share/elasticsearch/artifacts

RUN \
    bash -c "./el9-container-hardening.sh"; \
    wget https://security.almalinux.org/oval/org.almalinux.alsa-9.xml; \
    oscap oval eval --report elastic-alma9-cve-report.html org.almalinux.alsa-9.xml || :; \
    oscap ds sds-validate /usr/share/xml/scap/ssg/content/${BENCHMARK} \ && echo "ok" || echo "exit code = $? not ok"; \
    oscap xccdf eval --profile ${SCAP_PROFILE} --results elastic_alma9-${SCAP_SNAME}-scap-report.xml \
    --report elastic_alma9-${SCAP_SNAME}-scap-report.html /usr/share/xml/scap/ssg/content/${BENCHMARK} || :; \
    freshclam; \
    clamscan -r -v -i -l ./AV_scan.log --exclude-dir="^/sys" / || :; \
    chown elasticsearch:elasticsearch /usr/share/elasticsearch/artifacts; \
    grep -Hrn FOUND ./AV_scan.log; \
    microdnf remove -y clamav clamav-update openscap scap-security-guide wget bzip2; \
    microdnf clean all; \
    rm -rf /var/cache/dnf /tmp/* /var/tmp/*; \
    truncate -s 0 /var/log/*log

EXPOSE 9200 9300
ENTRYPOINT ["/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["eswrapper"]
USER elasticsearch:root
