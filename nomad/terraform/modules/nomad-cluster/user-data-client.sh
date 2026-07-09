#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

# Install dependencies
apt-get update
apt-get install -y unzip curl chrony podman crun slirp4netns cni-plugins logrotate awscli

# Install Nomad
curl -fsSL https://releases.hashicorp.com/nomad/${nomad_version}/nomad_${nomad_version}_linux_amd64.zip -o /tmp/nomad.zip
unzip /tmp/nomad.zip -d /usr/local/bin
chmod 0750 /usr/local/bin/nomad
chown nomad:nomad /usr/local/bin/nomad

# Create Nomad user
useradd -r -s /sbin/nologin -M nomad

# Create directories
mkdir -p /etc/nomad.d /opt/nomad/data /var/log/nomad
chown -R nomad:nomad /etc/nomad.d /opt/nomad/data /var/log/nomad
chmod 0700 /etc/nomad.d /opt/nomad/data
chmod 0750 /var/log/nomad

# Retrieve secrets from AWS Secrets Manager
export AWS_REGION=${aws_region}
secrets=$(aws secretsmanager get-secret-value --secret-id ${secrets_arn} --query SecretString --output text)
vault_token=$(echo $secrets | jq -r '.vault_token')

# Configure Nomad
cat <<EOF > /etc/nomad.d/nomad.hcl
data_dir = "/opt/nomad/data"
log_level = "INFO"
bind_addr = "0.0.0.0"
region = "global"
datacenter = "dc1"
acl {
  enabled = true
}
client {
  enabled = true
  server_join {
    retry_join = ["provider=aws tag_key=NomadType tag_value=server"]
  }
}
%{ if podman_enabled }
plugin "nomad-driver-podman" {
  config {
    enabled = true
    socket_path = "/run/user/1000/podman/podman.sock"
    volumes_enabled = true
  }
}
%{ endif }
tls {
  http = true
  rpc = true
  ca_file = "/etc/nomad.d/ca.pem"
  cert_file = "/etc/nomad.d/nomad-cert.pem"
  key_file = "/etc/nomad.d/nomad-key.pem"
}
%{ if vault_address != "" }
vault {
  enabled = true
  address = "${vault_address}"
  token = "$${vault_token}"
  create_from_role = "nomad-cluster"
}
%{ endif }
telemetry {
  collection_interval = "1s"
  disable_hostname = true
  prometheus_metrics = true
  publish_allocation_metrics = true
  publish_node_metrics = true
}
EOF
chown nomad:nomad /etc/nomad.d/nomad.hcl
chmod 0600 /etc/nomad.d/nomad.hcl

# Generate TLS certificates, signed by a locally-generated CA. Clients trust
# the servers' CA out of band; in production replace this with certs issued
# by the same shared CA used in ../../ansible/roles/nomad/tasks/certificates.yml.
local_ip=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)
openssl genrsa -out /etc/nomad.d/ca-key.pem 4096
openssl req -x509 -new -nodes -key /etc/nomad.d/ca-key.pem -sha256 -days 365 -out /etc/nomad.d/ca.pem -subj "/CN=Nomad CA"
openssl genrsa -out /etc/nomad.d/nomad-key.pem 4096
openssl req -new -key /etc/nomad.d/nomad-key.pem -out /etc/nomad.d/nomad.csr -subj "/CN=${cluster_name}/O=Nomad" -addext "subjectAltName=IP:$${local_ip},DNS:localhost,IP:127.0.0.1"
openssl x509 -req -in /etc/nomad.d/nomad.csr -CA /etc/nomad.d/ca.pem -CAkey /etc/nomad.d/ca-key.pem -CAcreateserial -out /etc/nomad.d/nomad-cert.pem -days 365 -sha256 -extfile <(echo "subjectAltName=IP:$${local_ip},DNS:localhost,IP:127.0.0.1")
chown nomad:nomad /etc/nomad.d/*.pem /etc/nomad.d/*.csr
chmod 0600 /etc/nomad.d/*.pem /etc/nomad.d/*.csr

# Configure logrotate
cat <<EOF > /etc/logrotate.d/nomad
/var/log/nomad/nomad.log {
  daily
  rotate 7
  compress
  delaycompress
  missingok
  notifempty
  create 0640 nomad nomad
  postrotate
    /bin/kill -HUP \$(pidof nomad) 2> /dev/null || true
  endscript
}
EOF
chown root:root /etc/logrotate.d/nomad
chmod 0644 /etc/logrotate.d/nomad

# Configure systemd service
cat <<EOF > /etc/systemd/system/nomad.service
[Unit]
Description=Nomad
Documentation=https://www.nomadproject.io/docs
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/local/bin/nomad agent -config=/etc/nomad.d/nomad.hcl
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=5
User=nomad
Group=nomad
LimitNOFILE=65536
LimitNPROC=4096
StandardOutput=append:/var/log/nomad/nomad.log
StandardError=append:/var/log/nomad/nomad.log
Environment="NOMAD_ADDR=https://0.0.0.0:4646"
Environment="NOMAD_CACERT=/etc/nomad.d/ca.pem"
PIDFile=/run/nomad.pid

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable nomad
systemctl start nomad
