## HAProxy SSL Frontend for Kibana

```sh

# Install certbot
sudo dnf install epel-release -y
sudo dnf install certbot -y

# Create certs dir and kibana cert
sudo mkdir certs
sudo certbot certonly --standalone -d kibana.demo.io -d kibana.demo.io
sudo mv /etc/letsencrypt/live/kibana.demo.io/fullchain.pem ./certs

#selinux
sudo setsebool -P haproxy_connect_any=1

#compose up
podman-compose up -d

```