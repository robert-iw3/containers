ARG BASE_REGISTRY=docker.io
ARG BASE_IMAGE=redhat/ubi9
ARG BASE_TAG=latest

FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_TAG} AS builder

# `tini` is a tiny but valid init for containers. This is used to cleanly
# control how ES and any child processes are shut down.
RUN \
    yum update -y; \
    yum install -y curl; \
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
    chmod 0555 /bin/tini; \
    mkdir /usr/share/elasticsearch

WORKDIR /usr/share/elasticsearch

RUN \
    curl --retry 10 -S -L --output /tmp/elasticsearch.tar.gz \
        https://artifacts-no-kpi.elastic.co/downloads/elasticsearch/elasticsearch-9.2.0-linux-$(arch).tar.gz; \
    tar -zxf /tmp/elasticsearch.tar.gz --strip-components=1

# The distribution includes a `config` directory, no need to create it
COPY scripts/elasticsearch.yml config/
COPY scripts/log4j2.properties config/log4j2.docker.properties

#  1. Configure the distribution for Docker
#  2. Create required directory
#  3. Move the distribution's default logging config aside
#  4. Move the generated docker logging config so that it is the default
#  5. Reset permissions on all directories
#  6. Reset permissions on all files
#  7. Make CLI tools executable
#  8. Make some directories writable. `bin` must be writable because
#     plugins can install their own CLI utilities.
#  9. Make some files writable
RUN \
    sed -i -e 's/ES_DISTRIBUTION_TYPE=tar/ES_DISTRIBUTION_TYPE=docker/' bin/elasticsearch-env; \
    mkdir data; \
    mv config/log4j2.properties config/log4j2.file.properties; \
    mv config/log4j2.docker.properties config/log4j2.properties; \
    find . -type d -exec chmod 0555 {} +; \
    find . -type f -exec chmod 0444 {} +; \
    chmod 0555 bin/* jdk/bin/* jdk/lib/jspawnhelper modules/x-pack-ml/platform/linux-*/bin/*; \
    chmod 0775 bin config config/jvm.options.d data logs plugins; \
    find config -type f -exec chmod 0664 {} +

################################################################################
# Build stage 2 (the actual Elasticsearch image):
#
# Copy elasticsearch from stage 1
# Add entrypoint
################################################################################

FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_TAG}

RUN yum update --setopt=tsflags=nodocs -y; \
    yum install --setopt=tsflags=nodocs -y \
      nc shadow-utils zip findutils unzip procps-ng; \
    yum clean all

RUN groupadd -g 1000 elasticsearch; \
    adduser -u 1000 -g 1000 -G 0 -d /usr/share/elasticsearch elasticsearch; \
    chown -R 0:0 /usr/share/elasticsearch

ENV ELASTIC_CONTAINER true

WORKDIR /usr/share/elasticsearch

COPY --from=builder --chown=0:0 /usr/share/elasticsearch /usr/share/elasticsearch

COPY --from=builder --chown=0:0 /bin/tini /bin/tini

ENV PATH /usr/share/elasticsearch/bin:$PATH
ENV SHELL /bin/bash
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# 1. Sync the user and group permissions of /etc/passwd
# 2. Set correct permissions of the entrypoint
# 3. Ensure that there are no files with setuid or setgid, in order to mitigate "stackclash" attacks.
#    We've already run this in previous layers so it ought to be a no-op.
# 4. Replace OpenJDK's built-in CA certificate keystore with the one from the OS
#    vendor. The latter is superior in several ways.
#    REF: https://github.com/elastic/elasticsearch-docker/issues/171
# 5. Tighten up permissions on the ES home dir (the permissions of the contents are handled earlier)
# 6. You can't install plugins that include configuration when running as `elasticsearch` and the `config`
#    dir is owned by `root`, because the installed tries to manipulate the permissions on the plugin's
#    config directory.
RUN chmod g=u /etc/passwd; \
    chmod 0555 /usr/local/bin/docker-entrypoint.sh; \
    find / -xdev -perm -4000 -exec chmod ug-s {} +; \
    chmod 0775 /usr/share/elasticsearch; \
    chown elasticsearch bin config config/jvm.options.d data logs plugins

RUN ln -sf /etc/pki/ca-trust/extracted/java/cacerts /usr/share/elasticsearch/jdk/lib/security/cacerts

EXPOSE 9200 9300

# Our actual entrypoint is `tini`, a minimal but functional init program. It
# calls the entrypoint we provide, while correctly forwarding signals.
ENTRYPOINT ["/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
# Dummy overridable parameter parsed by entrypoint
CMD ["eswrapper"]

USER 1000:0

HEALTHCHECK --interval=10s --timeout=5s --start-period=1m --retries=5 CMD curl -I -f --max-time 5 http://localhost:9200 || exit 1
