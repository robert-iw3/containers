FROM docker.io/node:24 AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
ENV REACT_APP_API_URL=https://nessus.testing.io/api
ENV REACT_APP_NESSUS_API_KEYS_FILE=/run/secrets/nessus_api_keys
RUN npm run build:css && npm run build

FROM docker.io/nginx:1.27
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]