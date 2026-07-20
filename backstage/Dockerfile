# syntax=docker/dockerfile:1
# Production Backstage portal image.
#
# Stage 1 scaffolds a Backstage app with create-app, adds the pg driver, and
# builds the backend bundle (the backend also serves the compiled frontend on
# port 7007 via plugin-app-backend). Stage 2 is a production-only install run
# as the unprivileged node user; entrypoint.sh pulls live secrets from Vault
# before exec'ing the backend.
ARG repo="docker.io/library"
ARG base_image="node:24-bookworm-slim"
ARG image_hash="d45d78e7929b46875bbd4e29bea672d5bc48186c6c3588306521c815e78352d6"

FROM ${repo}/${base_image}@sha256:${image_hash} AS builder

ARG CREATE_APP_VERSION=latest
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    YARN_HTTP_TIMEOUT=600000

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        python3 g++ make git ca-certificates build-essential libsqlite3-dev && \
    corepack enable

WORKDIR /work
RUN echo "backstage" | npx --yes @backstage/create-app@${CREATE_APP_VERSION} --skip-install

WORKDIR /work/backstage
RUN yarn install

# pg: the catalog database driver. oidc-provider: Keycloak SSO backend
# module. core-app-api: OAuth2 client used by the patched sign-in page.
RUN yarn workspace backend add pg @backstage/plugin-auth-backend-module-oidc-provider && \
    yarn workspace app add @backstage/core-app-api

# Wire the OIDC (Keycloak) sign-in page into the new frontend system and the
# oidc provider module into the backend.
COPY patches/App.tsx packages/app/src/App.tsx
RUN sed -i "s|backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));|backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));\nbackend.add(import('@backstage/plugin-auth-backend-module-oidc-provider'));|" \
        packages/backend/src/index.ts && \
    grep -q 'auth-backend-module-oidc-provider' packages/backend/src/index.ts

# The frontend bakes app.baseUrl and friends in at build time, so the real
# portal config must be present before build:backend. Kept below the install
# layers so config edits don't invalidate them.
COPY app-config.yaml ./app-config.yaml

RUN yarn tsc && yarn build:backend

RUN mkdir -p packages/backend/dist/skeleton packages/backend/dist/bundle && \
    tar xzf packages/backend/dist/skeleton.tar.gz -C packages/backend/dist/skeleton && \
    tar xzf packages/backend/dist/bundle.tar.gz -C packages/backend/dist/bundle && \
    [ -f .yarnrc.yml ] || touch .yarnrc.yml && \
    [ -d .yarn ] || mkdir .yarn && \
    [ -f backstage.json ] || echo '{}' > backstage.json

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    YARN_HTTP_TIMEOUT=600000

# python3/g++/make: native module builds (isolated-vm for the scaffolder,
# better-sqlite3). curl + ca-certificates: Vault API calls in entrypoint.sh
# and the container healthcheck.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        python3 g++ make build-essential libsqlite3-dev curl ca-certificates && \
    corepack enable

USER node
WORKDIR /app

COPY --from=builder --chown=node:node /work/backstage/.yarn ./.yarn
COPY --from=builder --chown=node:node /work/backstage/.yarnrc.yml /work/backstage/backstage.json ./
COPY --from=builder --chown=node:node /work/backstage/yarn.lock /work/backstage/package.json /work/backstage/packages/backend/dist/skeleton/ ./

RUN yarn workspaces focus --all --production && rm -rf "$(yarn cache clean 2>/dev/null; echo /home/node/.yarn/berry/cache)"

COPY --from=builder --chown=node:node /work/backstage/packages/backend/dist/bundle/ ./
COPY --chown=node:node app-config.yaml entrypoint.sh ./

ENV NODE_ENV=production
EXPOSE 7007
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s \
    CMD curl -sf http://127.0.0.1:7007/.backstage/health/v1/liveness || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
