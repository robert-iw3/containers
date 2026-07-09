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

FROM docker.io/nginx:1.27-alpine
COPY --from=build /app/elements/dist/elements.js /usr/share/nginx/html
COPY --from=build /app/frontend-sdk/dist/sdk.* /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    apk add --no-cache curl
EXPOSE 80
USER nginx
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD ["curl", "-f", "http://localhost/health"]
CMD ["nginx", "-g", "daemon off;"]