# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="node:current-alpine3.22" \
    image_hash="5d6348389bac182393e2ebaf08e434eb805bee6de0aba983ff53535cbc62c94d"

FROM ${repo}/${base_image}@sha256:${image_hash} AS build

WORKDIR /app
RUN apk add --no-cache git && \
    npm install -g npm@10.8.3

COPY package*.json ./
RUN npm ci --silent

COPY . .
RUN npm run build:elements

# nginx-unprivileged runs as uid 101 and listens on 8080, so the
# container works without root or CAP_NET_BIND_SERVICE.
FROM docker.io/nginxinc/nginx-unprivileged:1.27-alpine
USER root
RUN apk add --no-cache curl
COPY --from=build --chown=nginx:nginx /app/elements/dist/elements.js /usr/share/nginx/html/
COPY --from=build --chown=nginx:nginx /app/frontend-sdk/dist/sdk.* /usr/share/nginx/html/
COPY --chown=nginx:nginx nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
USER nginx
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD ["curl", "-f", "http://localhost:8080/health"]
CMD ["nginx", "-g", "daemon off;"]