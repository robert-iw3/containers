ARG ENV_MODE=prod
FROM docker.io/node:20-alpine AS builder
WORKDIR /app
COPY front-end/package*.json ./
RUN npm ci --only=production
COPY front-end/ ./
RUN if [ "$ENV_MODE" = "prod" ]; then npm run build; else echo "Dev mode - skipping build"; fi

FROM docker.io/nginx:alpine
RUN addgroup -g 1001 -S nginx && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8505
USER nginx  # Run as non-root
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8505 || exit 1
CMD ["nginx", "-g", "daemon off;"]