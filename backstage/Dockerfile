# syntax=docker/dockerfile:1
ARG repo="docker.io"
ARG base_image="node:24-alpine3.24"
ARG image_hash="4ba75f835bb8802193e4c114572113d4b26f95f6f094f4b5229d2a77773e0afc"

FROM ${repo}/${base_image}@sha256:${image_hash} AS builder

WORKDIR /app

ARG NPM_VERSION=11.18.0

RUN \
    apk add --no-cache python3 git; \
    npm install -g npm@${NPM_VERSION} yarn; \
    echo "backstage" | npx --yes @backstage/create-app@latest; \
    yarn --cwd /app/backstage add pg

FROM ${repo}/${base_image}

RUN \
    addgroup -S backstage; \
    adduser -S -G backstage backstage; \
    mkdir /app; \
    chown backstage:backstage /app

USER backstage
WORKDIR /app
COPY --from=builder --chown=backstage:backstage /app/backstage /app

EXPOSE 3000 7007
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1
ENTRYPOINT ["/bin/sh", "-c", "yarn dev"]