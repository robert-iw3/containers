server {
    listen 80;
    server_name nessus.testing.io;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name nessus.testing.io;

    ssl_certificate /etc/ssl/certs/nessus.testing.io.crt;
    ssl_certificate_key /etc/ssl/private/nessus.testing.io.key;
    ssl_dhparam /etc/nginx/dhparam.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    location / {
        proxy_pass https://nessus:8834;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}