# syntax=docker/dockerfile:1
# gitea: Git with a cup of tea!
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

RUN apk --no-cache add \
        bash \
        ca-certificates \
        curl \
        gettext \
        git \
        linux-pam \
        openssh \
        s6 \
        sqlite \
        su-exec \
        gnupg; \
    rm -rf /var/cache/apk/*; \
    \
    addgroup -S -g 1000 git; \
    adduser -S -H -D -h /data/git -s /bin/bash -u 1000 -G git git; \
    echo "git:*" | chpasswd -e

FROM base AS build-env

ARG GOPROXY
ENV GOPROXY ${GOPROXY:-direct}
ENV GOPATH /usr/local/bin/go
ARG GITEA_VERSION=v1.26.4
ARG TAGS="sqlite sqlite_unlock_notify"
ENV TAGS "bindata timetzdata $TAGS"
ARG CGO_EXTRA_CFLAGS
ARG SNYK_API

RUN \
    apk --no-cache add -t .gitea-deps \
        build-base \
        git \
        go \
        nodejs \
        npm \
        tzdata; \
    rm -rf /var/cache/apk/*; \
    mkdir -p ${GOPATH}/src/code.gitea.io

WORKDIR ${GOPATH}/src/code.gitea.io

# Clone, run snyk scan, and checkout version if set
RUN \
    git clone https://github.com/go-gitea/gitea.git; \
#    npm install -g snyk; \
#    npm install -g snyk-to-html; \
#    snyk config set api=${SNYK_API}; \
    cd gitea; \
#    snyk code test --json | snyk-to-html -o /gitea-code-review.html; \
#    snyk test --json | snyk-to-html -o /gitea-deps.html; \
#    snyk monitor; \
#    npm uninstall -g snyk; \
#    npm uninstall -g snyk-to-html; \
    if [ -n "${GITEA_VERSION}" ]; then git checkout "${GITEA_VERSION}"; fi; \
    make clean-all build; \
    go build contrib/environment-to-ini/environment-to-ini.go

# Copy local files
COPY docker/root /tmp/local

# Set permissions
RUN chmod 0755 \
    /tmp/local/usr/bin/entrypoint \
    /tmp/local/usr/local/bin/gitea \
    /tmp/local/etc/s6/gitea/* \
    /tmp/local/etc/s6/openssh/* \
    /tmp/local/etc/s6/.s6-svscan/* \
    /go/src/code.gitea.io/gitea/gitea \
    /go/src/code.gitea.io/gitea/environment-to-ini; \
    \
    chmod 644 /go/src/code.gitea.io/gitea/contrib/autocompletion/bash_autocomplete

FROM base

ENV USER git
ENV GITEA_CUSTOM /data/gitea
ENV TINI_VERSION v0.19.0

#COPY --from=build-env /gitea-code-review.html /
#COPY --from=build-env /gitea-deps.html /
COPY --from=build-env /tmp/local /
COPY --from=build-env /usr/local/bin/go/src/code.gitea.io/gitea/gitea /app/gitea/gitea
COPY --from=build-env /usr/local/bin/go/src/code.gitea.io/gitea/environment-to-ini /usr/local/bin/environment-to-ini
COPY --from=build-env /usr/local/bin/go/src/code.gitea.io/gitea/contrib/autocompletion/bash_autocomplete /etc/profile.d/gitea_bash_autocomplete.sh
COPY --chmod=755 entrypoint.sh /usr/bin/

RUN \
    tini_bin="" ; \
    case "$(arch)" in \
        aarch64) tini_bin='tini-arm64' ;; \
        x86_64)  tini_bin='tini-amd64' ;; \
        *) echo >&2 ; echo >&2 "Unsupported architecture $(arch)" ; echo >&2 ; exit 1 ;; \
    esac ; \
    curl --retry 10 -S -L -O https://github.com/krallin/tini/releases/download/${TINI_VERSION}/${tini_bin} ; \
    curl --retry 10 -S -L -O https://github.com/krallin/tini/releases/download/${TINI_VERSION}/${tini_bin}.sha256sum ; \
    sha256sum -c ${tini_bin}.sha256sum ; \
    rm ${tini_bin}.sha256sum ; \
    mv ${tini_bin} /usr/bin/tini ; \
    chmod 0555 /usr/bin/tini; \
    \
    apk add --no-cache -t .av-scan \
        clamav \
        freshclam; \
    \
    DATE=$(date '+%Y-%m-%d %H:%M:%S'); \
    freshclam; \
    clamscan -rvi -l /clamav_scan_${DATE}.log --exclude-dir="^/sys|^/dev" /; \
    apk del --no-network --purge .av-scan; \
    rm -rf /var/cache/apk/*

EXPOSE 22 3000
VOLUME ["/data"]
ENTRYPOINT ["/usr/bin/tini", \
            "--", \
            "/usr/bin/entrypoint.sh"]
CMD ["/bin/s6-svscan", "/etc/s6"]