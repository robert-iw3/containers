FROM ubuntu:24.04 AS builder

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl

RUN cd /tmp && \
  curl --retry 8 -s -L \
    --output kibana.tar.gz \
     https://artifacts.elastic.co/downloads/kibana/kibana-8.17.0-linux-$(arch).tar.gz && \
  cd -

RUN mkdir /usr/share/kibana
WORKDIR /usr/share/kibana
RUN tar \
  --strip-components=1 \
  -zxf /tmp/kibana.tar.gz

RUN chmod -R g=u /usr/share/kibana

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
RUN mkdir -p /usr/share/fonts/local && \
  curl --retry 8 -S -L -o /usr/share/fonts/local/NotoSansCJK-Regular.ttc https://github.com/googlefonts/noto-cjk/raw/NotoSansV2.001/NotoSansCJK-Regular.ttc && \
  echo "5dcd1c336cc9344cb77c03a0cd8982ca8a7dc97d620fd6c9c434e02dcb1ceeb3  /usr/share/fonts/local/NotoSansCJK-Regular.ttc" | sha256sum -c -


FROM ubuntu:24.04
EXPOSE 5601

RUN for iter in {1..10}; do \
      export DEBIAN_FRONTEND=noninteractive && \
      apt-get update  && \
      apt-get upgrade -y  && \
      apt-get install -y --no-install-recommends \
       fontconfig libnss3 curl ca-certificates && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/* && exit_code=0 && break || exit_code=$? && echo "apt-get error: retry $iter in 10s" && \
      sleep 10; \
    done; \
    (exit $exit_code)

COPY --from=builder --chown=1000:0 /usr/share/kibana /usr/share/kibana
COPY --from=builder --chown=0:0 /bin/tini /bin/tini

COPY --from=builder --chown=0:0 /usr/share/fonts/local/NotoSansCJK-Regular.ttc /usr/share/fonts/local/NotoSansCJK-Regular.ttc
RUN fc-cache -v
WORKDIR /usr/share/kibana
RUN ln -s /usr/share/kibana /opt/kibana

ENV ELASTIC_CONTAINER true
ENV PATH=/usr/share/kibana/bin:$PATH

COPY --chown=1000:0 config/kibana.yml /usr/share/kibana/config/kibana.yml

COPY bin/kibana-docker /usr/local/bin/

RUN chmod g+ws /usr/share/kibana && \
    find /usr/share/kibana -gid 0 -and -not -perm /g+w -exec chmod g+w {} \;

RUN find / -xdev -perm -4000 -exec chmod u-s {} +

RUN groupadd --gid 1000 kibana && \
    useradd --uid 1000 --gid 1000 -G 0 \
      --home-dir /usr/share/kibana --no-create-home \
      kibana

ENTRYPOINT ["/bin/tini", "--"]

CMD ["/usr/local/bin/kibana-docker"]

USER 1000
