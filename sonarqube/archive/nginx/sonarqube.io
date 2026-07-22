server {
    listen 443 ssl;
    listen [::]:443 ssl;
    include snippets/sonarqube.conf;
    include snippets/ssl-params.conf;

    root /var/www/sonarqube.io/html;
    index index.html index.htm index.nginx-debian.html;

    server_name sonarqube.io www.sonarqube.io;

    location / {
                try_files $uri $uri/ =404;
        }
}

server {
    listen 80;
    listen [::]:80;

    server_name sonarqube.io www.sonarqube.io;

    return 301 https://$server_name$request_uri;
}
