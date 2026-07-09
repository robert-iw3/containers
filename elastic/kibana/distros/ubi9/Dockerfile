ARG BASE_REGISTRY=docker.io
ARG BASE_IMAGE=redhat/ubi9
ARG BASE_TAG=latest

FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_TAG} as kibana_files

RUN \
      yum update --setopt=tsflags=nodocs -y; \
      yum install -y \
            curl \
            tar \
            gzip; \
      yum clean all; \
      curl --retry 8 -s -L \
            --output /tmp/kibana.tar.gz \
            https://artifacts.elastic.co/downloads/kibana/kibana-9.2.0-linux-$(arch).tar.gz; \


RUN mkdir /usr/share/kibana
WORKDIR /usr/share/kibana

# Ensure that group permissions are the same as user permissions.
# This will help when relying on GID-0 to run Kibana, rather than UID-1000.
# OpenShift does this, for example.
# REF: https://docs.openshift.org/latest/creating_images/guidelines.html
RUN \
      tar \
      --strip-components=1 \
      -zxf /tmp/kibana.tar.gz; \
      chmod -R g=u /usr/share/kibana

################################################################################
# Build stage 1
# Copy prepared files from the previous stage and complete the image.
################################################################################
FROM ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_TAG}
EXPOSE 5601

# Add a dumb init process
RUN \
      yum update --setopt=tsflags=nodocs -y; \
      yum install -y \
            fontconfig \
            freetype \
            shadow-utils \
            nss; \
      yum clean all; \
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


# Noto Fonts
RUN \
      mkdir /usr/share/fonts/local; \
      curl --retry 8 -S -L -o /usr/share/fonts/local/NotoSansCJK-Regular.ttc \
            https://github.com/googlefonts/noto-cjk/raw/NotoSansV2.001/NotoSansCJK-Regular.ttc; \
      echo "5dcd1c336cc9344cb77c03a0cd8982ca8a7dc97d620fd6c9c434e02dcb1ceeb3  \
            /usr/share/fonts/local/NotoSansCJK-Regular.ttc" | sha256sum -c -; \
      fc-cache -v

# Bring in Kibana from the initial stage.
COPY --from=kibana_files --chown=1000:0 /usr/share/kibana /usr/share/kibana
WORKDIR /usr/share/kibana
RUN ln -s /usr/share/kibana /opt/kibana

ENV ELASTIC_CONTAINER true
ENV PATH=/usr/share/kibana/bin:$PATH

# Set some Kibana configuration defaults.
COPY --chown=1000:0 config/kibana.yml /usr/share/kibana/config/kibana.yml

# Add the launcher/wrapper script. It knows how to interpret environment
# variables and translate them to Kibana CLI options.
COPY --chmod=755 bin/kibana-docker /usr/local/bin/

# Remove the suid bit everywhere to mitigate "Stack Clash"
RUN \
      find / -xdev -perm -4000 -exec chmod u-s {} +; \
      groupadd --gid 1000 kibana; \
      useradd --uid 1000 --gid 1000 -G 0 \
      --home-dir /usr/share/kibana --no-create-home \
      kibana

USER kibana

ENTRYPOINT ["/bin/tini", "--"]

CMD ["/usr/local/bin/kibana-docker"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=1m --retries=5 CMD curl -I -f --max-time 5 http://localhost:5601 || exit 1
