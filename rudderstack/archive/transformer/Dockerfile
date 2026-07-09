# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="483f502c0e6aff6d80a807f25d3f88afa40439c29fdd2d21a0912e0f42db842a"

# build node from source
FROM ${repo}/${base_image}@sha256:${image_hash} AS node-base

ENV NODE_VERSION 21.4.0

RUN \
    addgroup -g 1000 node; \
    adduser -u 1000 -G node -s /bin/sh -D node; \
    apk add --no-cache \
        libstdc++; \
    apk add --no-cache --virtual .build-deps \
        curl; \
    ARCH= OPENSSL_ARCH='linux*' alpineArch="$(apk --print-arch)"; \
      case "${alpineArch##*-}" in \
        x86_64) ARCH='x64' CHECKSUM="10b7b23b6b867a25f060a433b83f5c3ecb3bcf7cdba1c0ce46443065a832fd41" OPENSSL_ARCH=linux-x86_64;; \
        x86) OPENSSL_ARCH=linux-elf;; \
        aarch64) OPENSSL_ARCH=linux-aarch64;; \
        arm*) OPENSSL_ARCH=linux-armv4;; \
        ppc64le) OPENSSL_ARCH=linux-ppc64le;; \
        s390x) OPENSSL_ARCH=linux-s390x;; \
        *) ;; \
      esac; \
  if [ -n "${CHECKSUM}" ]; then \
    curl -fsSLO --compressed "https://unofficial-builds.nodejs.org/download/release/v$NODE_VERSION/node-v$NODE_VERSION-linux-$ARCH-musl.tar.xz"; \
    echo "$CHECKSUM  node-v$NODE_VERSION-linux-$ARCH-musl.tar.xz" | sha256sum -c - ; \
      tar -xJf "node-v$NODE_VERSION-linux-$ARCH-musl.tar.xz" -C /usr/local --strip-components=1 --no-same-owner; \
      ln -s /usr/local/bin/node /usr/local/bin/nodejs; \
  else \
    echo "Building from source"; \
    # backup build
    apk add --no-cache --virtual .build-deps-full \
        binutils-gold \
        g++ \
        gcc \
        gnupg \
        libgcc \
        linux-headers \
        make \
        python3; \
    # use pre-existing gpg directory, see https://github.com/nodejs/docker-node/pull/1895#issuecomment-1550389150
    export GNUPGHOME="$(mktemp -d)"; \
    # gpg keys listed at https://github.com/nodejs/node#release-keys
    for key in \
      4ED778F539E3634C779C87C6D7062848A1AB005C \
      141F07595B7B3FFE74309A937405533BE57C7D57 \
      74F12602B6F1C4E913FAA37AD3A89613643B6201 \
      DD792F5973C6DE52C432CBDAC77ABFA00DDBF2B7 \
      61FC681DFB92A079F1685E77973F295594EC4689 \
      8FCCA13FEF1D0C2E91008E09770F7A9A5AE15600 \
      C4F0DFFF4E8C1A8236409D08E73BC641CC11F4C8 \
      890C08DB8579162FEE0DF9DB8BEAB4DFCF555EF4 \
      C82FA3AE1CBEDC6BE46B9360C43CEC45C17AB93C \
      108F52B48DB57BB0CC439B2997B01419BD92F80A \
      A363A499291CBBC940DD62E41F10027AF002F8B0 \
    ; do \
      gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$key" || \
      gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "$key" ; \
    done; \
    curl -fsSLO --compressed "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION.tar.xz"; \
    curl -fsSLO --compressed "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt.asc"; \
    gpg --batch --decrypt --output SHASUMS256.txt SHASUMS256.txt.asc; \
    gpgconf --kill all; \
    rm -rf "$GNUPGHOME"; \
    grep " node-v$NODE_VERSION.tar.xz\$" SHASUMS256.txt | sha256sum -c -; \
    tar -xf "node-v$NODE_VERSION.tar.xz"; \
    cd "node-v$NODE_VERSION"; \
    ./configure; \
    make -j$(getconf _NPROCESSORS_ONLN) V=; \
    make install; \
    apk del .build-deps-full; \
    cd ..; \
    rm -Rf "node-v$NODE_VERSION"; \
    rm "node-v$NODE_VERSION.tar.xz" SHASUMS256.txt.asc SHASUMS256.txt; \
  fi; \
  rm -f "node-v$NODE_VERSION-linux-$ARCH-musl.tar.xz"; \
  # Remove unused OpenSSL headers to save ~34MB. See this NodeJS issue: https://github.com/nodejs/node/issues/46451
  find /usr/local/include/node/openssl/archs -mindepth 1 -maxdepth 1 ! -name "$OPENSSL_ARCH" -exec rm -rf {} \; ;\
  apk del .build-deps; \
  # smoke tests
  node --version; \
  npm --version

ENV YARN_VERSION 1.22.19

RUN apk add --no-cache --virtual .build-deps-yarn \
        curl \
        gnupg \
        tar; \
  # use pre-existing gpg directory, see https://github.com/nodejs/docker-node/pull/1895#issuecomment-1550389150
  export GNUPGHOME="$(mktemp -d)"; \
  for key in \
    6A010C5166006599AA17F08146C2130DFD2497F5 \
  ; do \
    gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$key" || \
    gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "$key" ; \
  done; \
  curl -fsSLO --compressed "https://yarnpkg.com/downloads/$YARN_VERSION/yarn-v$YARN_VERSION.tar.gz"; \
  curl -fsSLO --compressed "https://yarnpkg.com/downloads/$YARN_VERSION/yarn-v$YARN_VERSION.tar.gz.asc"; \
  gpg --batch --verify yarn-v$YARN_VERSION.tar.gz.asc yarn-v$YARN_VERSION.tar.gz; \
  gpgconf --kill all; \
  rm -rf "$GNUPGHOME"; \
  mkdir -p /opt; \
  tar -xzf yarn-v$YARN_VERSION.tar.gz -C /opt/; \
  ln -s /opt/yarn-v$YARN_VERSION/bin/yarn /usr/local/bin/yarn; \
  ln -s /opt/yarn-v$YARN_VERSION/bin/yarnpkg /usr/local/bin/yarnpkg; \
  rm yarn-v$YARN_VERSION.tar.gz.asc yarn-v$YARN_VERSION.tar.gz; \
  apk del .build-deps-yarn; \
  # smoke test
  yarn --version

COPY node-docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["node-docker-entrypoint.sh"]

CMD [ "node" ]

# base image from node build
FROM node-base AS base

ENV HUSKY 0

RUN \
    apk update; apk upgrade; \
    apk add --no-cache \
        tini \
        make \
        g++ \
        git \
        python3; \
    mkdir -p /home/node/app/node_modules; \
    chown -R node:node /home/node/app

FROM base AS development

ENV HUSKY 0

ARG version
ARG GIT_COMMIT_SHA
ENV transformer_build_version=$version
ENV git_commit_sha=$GIT_COMMIT_SHA

# Create app directory, clone source files
WORKDIR /home/node/app
RUN \
    chown -R node:node /home/node/app; \
    git clone https://github.com/rudderlabs/rudder-transformer.git; \
    cp rudder-transformer/package*.json ./; \
    cp scripts/skipPrepareScript.js ./scripts/skipPrepareScript.js; \
    chown -R node:node /home/node/app

USER node

RUN \
    npm ci --no-audit --cache .npm; \
    npm run build:ci -- --sourceMap false; \
    npm run copy; \
    npm run setup:swagger

ENTRYPOINT ["/sbin/tini", "--"]

HEALTHCHECK --interval=1s --timeout=30s --retries=30 \
    CMD wget --no-verbose --tries=5 --spider http://localhost:9090/health || exit 1

CMD [ "npm", "start" ]

EXPOSE 9090/tcp

FROM base AS prodDepsBuilder

WORKDIR /home/node/app
USER node
COPY --chown=node:node --from=development /home/node/app/package*.json ./
COPY --chown=node:node --from=development /home/node/app/scripts/skipPrepareScript.js ./scripts/skipPrepareScript.js

ENV SKIP_PREPARE_SCRIPT='true'

RUN npm ci --omit=dev --no-audit --cache .npm
RUN npm run clean:node

# final image
FROM base as production

ENV HUSKY 0

ARG version
ARG GIT_COMMIT_SHA
ENV transformer_build_version=$version
ENV git_commit_sha=$GIT_COMMIT_SHA

WORKDIR /home/node/app

USER node

COPY --chown=node:node --from=prodDepsBuilder /home/node/app/package.json ./
COPY --chown=node:node --from=prodDepsBuilder /home/node/app/node_modules ./node_modules
COPY --chown=node:node --from=development /home/node/app/dist/ ./dist

ENTRYPOINT ["/sbin/tini", "--"]

HEALTHCHECK --interval=1s --timeout=30s --retries=30 \
CMD wget --no-verbose --tries=5 --spider http://localhost:9090/health || exit 1

CMD [ "npm", "start" ]

EXPOSE 9090/tcp