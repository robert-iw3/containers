FROM node:24-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY src ./src
COPY public ./public

RUN npm run build

FROM cgr.dev/chainguard/nginx:latest

COPY --from=build /app/build /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

ENTRYPOINT ["/usr/sbin/nginx"]
CMD ["-g", "daemon off;"]
