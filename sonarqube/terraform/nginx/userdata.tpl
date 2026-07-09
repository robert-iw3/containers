#!/usr/bin/env bash

#cloud-config

apt update -y && apt install nginx -y

tee /usr/share/nginx/html/index.html <<EOF
<!DOCTYPE html>
<html>
<head>
  <title>StackPath - Amazon Web Services Instance</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8">
  <style>
    html, body {
      background: #000;
      height: 100%;
      width: 100%;
      padding: 0;
      margin: 0;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-flow: column;
    }
    img { width: 250px; }
    svg { padding: 0 40px; }
    p {
      color: #fff;
      font-family: 'Courier New', Courier, monospace;
      text-align: center;
      padding: 10px 30px;
    }
  </style>
</head>
<body>
  <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS83vGYYzj5AjHAK_5jBwaXUE7960vtulm6rQ&usqp=CAU">
  <p>This request was proxied from <strong>Amazon Web Services</strong></p>
</body>
</html>
EOF

chmod 0644 /usr/share/nginx/html/index.html

tee /etc/nginx/conf.d/default.conf << EOF
# Based on https://www.nginx.com/resources/wiki/start/topics/examples/full/#nginx-conf
# user              www www;  ## Default: nobody

worker_processes  auto;
error_log         "/var/log/nginx/logs/error.log";

events {
    worker_connections  2048;
}

http {
    default_type    application/octet-stream;
    log_format      main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log      "/var/log/nginx/logs/access.log" main;
    add_header      X-Frame-Options SAMEORIGIN;
    add_header      Strict-Transport-Security "max-age=31536000; includeSubdomains; preload";
    add_header      X-Content-Type-Options nosniff;
    add_header      X-XSS-Protection "1; mode=block";
    add_header      Referrer-Policy origin-when-cross-origin;
    add_header      Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    proxy_connect_timeout 180s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    proxy_buffer_size 512k;
    proxy_buffers 16 4m;
    proxy_busy_buffers_size 16m;

    sendfile           on;
    tcp_nopush         on;
    tcp_nodelay        off;
    gzip               on;
    gzip_http_version  1.0;
    gzip_comp_level    2;
    gzip_proxied       any;
    gzip_types         text/plain text/css application/javascript text/xml application/xml+rss;
    keepalive_timeout  65;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:DHE-RSA-AES256-SHA:ECDHE-ECDSA-DES-CBC3-SHA:ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:AES256-SHA:DES-CBC3-SHA:!DSS';
    ssl_stapling        on;
    ssl_stapling_verify on;
    ssl_session_cache   shared:SSL:50m;
    ssl_session_timeout 1d;

    client_max_body_size 100M;
    server_tokens off;

    absolute_redirect  off;
    port_in_redirect   off;

    include  "/opt/nginx/conf/server_blocks/*.conf";

    # HTTP Server
    server {
        # Port to listen on, can also be set in IP:PORT format
        listen  443;
        server_name sonarqube;
        include  "/opt/nginx/conf/*.conf";

        location /status {
            stub_status on;
            access_log   on;
            allow 127.0.0.1;
            deny all;
        }
        location / {
            autoindex on;
            ssi on;
        }
        location /sonarqube/ {
            proxy_pass http://sonarqube.io:9000/;
        }
    }
}
EOF

chmod 0644 /etc/nginx/conf.d/default.conf

tee /opt/nginx/conf/server_blocks/sonarqube.conf << EOF
server {
listen                        80;
listen                        [::]:80;
server_name                   sonarqube.io;
return 301                    https://$server_name$request_uri;
}
server {
listen 443                    ssl;
listen [::]:443               ssl;
client_max_body_size          100M;
server_name                   sonarqube.io;
ssl_certificate               /opt/nginx/conf/certs/sonarqube.crt;
ssl_certificate_key           /opt/nginx/conf/certs/sonarqube.key;
access_log                    /var/log/nginx/logs/sonarqube.access.log;
include                       "/opt/nginx/conf/*.conf";
location /sonarqube {
    proxy_set_header            Host $host;
    proxy_set_header            X-Real-IP $remote_addr;
    proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header            X-Forwarded-SSL on;
    proxy_set_header            X-Forwarded-Host $host;
    proxy_pass                  http://sonarqube.io:9000;
    proxy_max_temp_file_size    0;
    proxy_connect_timeout       120;
    proxy_send_timeout          90;
    proxy_read_timeout          90;
    proxy_buffer_size           8k;
    proxy_buffers               4 32k;
    proxy_busy_buffers_size     64k;
    proxy_temp_file_write_size  64k;
    client_body_buffer_size     1K;
    client_header_buffer_size   1k;
    client_max_body_size        1k;
    large_client_header_buffers 2 1k;
    }
}
EOF

chmod 0644 /opt/nginx/conf/server_blocks/sonarqube.conf
