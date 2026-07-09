FROM nginx:1.27.3-alpine3.20-slim

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 26257
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]