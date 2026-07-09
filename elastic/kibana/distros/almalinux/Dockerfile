FROM quay.io/almalinuxorg/almalinux:10 AS build-env

ARG ELASTIC_VERSION=9.4.3

RUN \
    dnf update -y; \
    dnf install -y npm; \
    cd /tmp; \
    curl --retry 8 -s -L \
    --output kibana.tar.gz \
    https://artifacts.elastic.co/downloads/kibana/kibana-${ELASTIC_VERSION}-linux-$(arch).tar.gz; \
    cd -

RUN \
    mkdir /usr/share/kibana; cd /usr/share/kibana; \
    tar --strip-components=1 -zxf /tmp/kibana.tar.gz; \
    chmod -R g=u /usr/share/kibana

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
#    wget https://github.com/elastic/kibana/archive/refs/tags/v${ELASTIC_VERSION}.tar.gz; \
#    tar zxvf v${ELASTIC_VERSION}.tar.gz; cd kibana-${ELASTIC_VERSION}; \
#    npm install -g snyk; \
#    npm install snyk-to-html -g; \
#    snyk config set api=${SNYK_API}; \
#    snyk code test --json | snyk-to-html -o /kibana-code-review.html; \
#    snyk test --json | snyk-to-html -o /kibana-deps.html; \
#    snyk monitor; \
#    npm uninstall -g snyk; \
#    npm uninstall -g snyk-to-html; \
#    dnf remove -y npm

RUN rm -rf /tmp/*

FROM quay.io/almalinuxorg/10-minimal:latest

RUN \
    useradd --uid 1000 --gid 0 \
    --home-dir /usr/share/kibana kibana; \
    microdnf install -y yum-utils epel-release; \
    dnf config-manager --set-enabled crb; \
    /usr/bin/crb enable; \
    microdnf update -y; \
    microdnf install -y \
        fontconfig \
        liberation-fonts \
        nss \
        ca-certificates \
        curl \
        clamav \
        clamav-update \
        openscap \
        scap-security-guide \
        wget \
        bzip2

RUN set -e ; \
    TINI_BIN="" ; \
    case "$(arch)" in \
        aarch64) \
            TINI_BIN='tini-arm64' ; \
            ;; \
        x86_64) \
            TINI_BIN='tini-amd64' ; \
            ;; \
        *) echo >&2 "Unsupported architecture $(arch)" ; exit 1 ;; \
    esac ; \
    TINI_VERSION='v0.19.0' ; \
    curl --retry 8 -S -L -O "https://github.com/krallin/tini/releases/download/${TINI_VERSION}/${TINI_BIN}" ; \
    curl --retry 8 -S -L -O "https://github.com/krallin/tini/releases/download/${TINI_VERSION}/${TINI_BIN}.sha256sum" ; \
    sha256sum -c "${TINI_BIN}.sha256sum" ; \
    rm "${TINI_BIN}.sha256sum" ; \
    mv "${TINI_BIN}" /bin/tini ; \
    chmod +x /bin/tini

RUN \
    mkdir /usr/share/fonts/local; \
    curl --retry 8 -S -L -o /usr/share/fonts/local/NotoSansCJK-Regular.ttc \
    https://github.com/googlefonts/noto-cjk/raw/NotoSansV2.001/NotoSansCJK-Regular.ttc; \
    echo "5dcd1c336cc9344cb77c03a0cd8982ca8a7dc97d620fd6c9c434e02dcb1ceeb3  /usr/share/fonts/local/NotoSansCJK-Regular.ttc" | sha256sum -c -; \
    fc-cache -v

COPY --from=build-env --chown=1000:0 /usr/share/kibana /usr/share/kibana
WORKDIR /usr/share/kibana
RUN ln -s /usr/share/kibana /opt/kibana

ENV ELASTIC_CONTAINER true
ENV PATH=/usr/share/kibana/bin:$PATH

COPY --chown=1000:0 config/kibana.yml /usr/share/kibana/config/kibana.yml

COPY bin/kibana-docker /usr/local/bin/

RUN chmod g+ws /usr/share/kibana
RUN find /usr/share/kibana -gid 0 -and -not -perm /g+w -exec chmod g+w {} \;

RUN find / -xdev -perm -4000 -exec chmod u-s {} +

WORKDIR /usr/share/kibana/artifacts

ARG SCAP_PROFILE=xccdf_org.ssgproject.content_profile_stig \
    SCAP_SNAME=STIG \
    BENCHMARK=ssg-almalinux9-ds.xml

COPY --chmod=755 el9-container-hardening.sh .
#COPY --chown=kibana:kibana --from=build-env /kibana-code-review.html /usr/share/kibana/artifacts
#COPY --chown=kibana:kibana --from=build-env /kibana-deps.html /usr/share/kibana/artifacts

RUN \
    bash -c "./el9-container-hardening.sh"; \
    wget https://security.almalinux.org/oval/org.almalinux.alsa-9.xml; \
    oscap oval eval --report kibana-alma9-cve-report.html org.almalinux.alsa-9.xml || :; \
    oscap ds sds-validate /usr/share/xml/scap/ssg/content/${BENCHMARK} \ && echo "ok" || echo "exit code = $? not ok"; \
    oscap xccdf eval --profile ${SCAP_PROFILE} --results kibana_alma9-${SCAP_SNAME}-scap-report.xml \
    --report kibana_alma9-${SCAP_SNAME}-scap-report.html /usr/share/xml/scap/ssg/content/${BENCHMARK} || :; \
    freshclam; \
    clamscan -rvi -l clamav_scan.log --exclude-dir="^/sys" / || :; \
    chown -R kibana:kibana /usr/share/kibana; \
    grep -Hrn FOUND clamav_scan.log; \
    microdnf remove -y clamav clamav-update openscap scap-security-guide wget bzip2; \
    microdnf clean all; \
    rm -rf /var/cache/dnf /var/cache/yum /tmp/* /var/tmp/*; \
    truncate -s 0 /var/log/*log; \
    chmod +x /usr/local/bin/kibana-docker

EXPOSE 5601
USER kibana
ENTRYPOINT ["/bin/tini", "--"]
CMD ["/usr/local/bin/kibana-docker"]
