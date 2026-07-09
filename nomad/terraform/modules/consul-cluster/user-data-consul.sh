#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

# Install dependencies
apt-get update
apt-get install -y unzip curl chrony logrotate

# Install Consul
curl -fsSL https://releases.hashicorp.com/consul/1.20.0/consul_1.20.0_linux_amd64.zip -o /tmp/consul.zip
unzip /tmp/consul.zip -d /usr/local/bin
chmod 0750 /usr/local/bin/consul
chown consul:consul /usr/local/bin/consul

# Create Consul user
useradd -r -s /sbin/nologin -M consul

# Create directories
mkdir -p /etc/consul.d /opt/consul/data /var/log/consul
chown -R consul:consul /etc/consul.d /opt/consul/data /var/log/consul
chmod 0700 /etc/consul.d /opt/consul/data
chmod 0750 /var/log/consul

# Configure Consul
cat <<EOF > /etc/consul.d/consul.hcl
data_dir = "/opt/consul/data"
log_level = "INFO"
bind_addr = "0.0.0.0"
client_addr = "0.0.0.0"
ports {
  http = 8500
  grpc = 8503
  grpc_tls = 8502
  serf_lan = 8301
  serf_wan = 8302
  server = 8300
}
server = true
bootstrap_expect = ${desired_capacity}
connect {
  enabled = true
}
retry_join = ["provider=aws tag_key=ConsulAutoJoin tag_value=auto-join"]
acl {
  enabled = true
  default_policy = "deny"
  enable_token_persistence = true
}
tls {
  defaults {
    ca_file = "/etc/consul.d/ca.pem"
    cert_file = "/etc/consul.d/consul-cert.pem"
    key_file = "/etc/consul.d/consul-key.pem"
  }
  internal_rpc {
    verify_incoming = true
    verify_outgoing = true
  }
  https {
    verify_incoming = false
    verify_outgoing = true
  }
}
auto_encrypt {
  enabled = true
}
EOF
chown consul:consul /etc/consul.d/consul.hcl
chmod 0600 /etc/consul.d/consul.hcl

# Generate TLS certificates
openssl genrsa -out /etc/consul.d/ca-key.pem 4096
openssl req -x509 -new -nodes -key /etc/consul.d/ca-key.pem -sha256 -days 365 -out /etc/consul.d/ca.pem -subj "/CN=Consul CA"
openssl genrsa -out /etc/consul.d/consul-key.pem 4096
openssl req -new -key /etc/consul.d/consul-key.pem -out /etc/consul.d/consul.csr -subj "/CN=${cluster_name}/O=Consul" -addext "subjectAltName=IP:$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4),DNS:localhost,IP:127.0.0.1"
openssl x509 -req -in /etc/consul.d/consul.csr -CA /etc/consul.d/ca.pem -CAkey /etc/consul.d/ca-key.pem -CAcreateserial -out /etc/consul.d/consul-cert.pem -days 365 -sha256 -extfile <(echo "subjectAltName=IP:$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4),DNS:localhost,IP:127.0.0.1")
chown consul:consul /etc/consul.d/*.pem /etc/consul.d/*.csr
chmod 0600 /etc/consul.d/*.pem /etc/consul.d/*.csr

# Configure Consul ACL policy
cat <<EOF > /etc/consul.d/nomad-policy.hcl
agent {
  policy = "read"
}
node {
  policy = "read"
}
service {
  policy = "write"
}
EOF
chown consul:consul /etc/consul.d/nomad-policy.hcl
chmod 0600 /etc/consul.d/nomad-policy.hcl

# Configure logrotate
cat <<EOF > /etc/logrotate.d/consul
/var/log/consul/consul.log {
  daily
  rotate 7
  compress
  delaycompress
  missingok
  notifempty
  create 0640 consul consul
  postrotate
    /bin/kill -HUP \$(pidof consul) 2> /dev/null || true
  endscript
}
EOF
chown root:root /etc/logrotate.d/consul
chmod 0644 /etc/logrotate.d/consul

# Configure systemd service
cat <<EOF > /etc/systemd/system/consul.service
[Unit]
Description=Consul
Documentation=https://www.consul.io/docs
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/local/bin/consul agent -config-dir=/etc/consul.d
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=5
User=consul
Group=consul
LimitNOFILE=65536
LimitNPROC=4096
StandardOutput=append:/var/log/consul/consul.log
StandardError=append:/var/log/consul/consul.log
Environment="CONSUL_HTTP_ADDR=https://0.0.0.0:8500"
Environment="CONSUL_CACERT=/etc/consul.d/ca.pem"

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable consul
systemctl start consul

# Bootstrap ACLs
consul acl bootstrap > /etc/consul.d/acl-bootstrap.txt
chown consul:consul /etc/consul.d/acl-bootstrap.txt
chmod 0600 /etc/consul.d/acl-bootstrap.txt

# Apply Nomad policy
CONSUL_TOKEN=$(grep 'SecretID' /etc/consul.d/acl-bootstrap.txt | awk '{print $NF}')
consul acl policy create -name nomad -rules @/etc/consul.d/nomad-policy.hcl -token $CONSUL_TOKEN