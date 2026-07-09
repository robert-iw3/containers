#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

# Install dependencies
apt-get update
apt-get install -y unzip curl chrony logrotate

# Install Vault
curl -fsSL https://releases.hashicorp.com/vault/1.17.2/vault_1.17.2_linux_amd64.zip -o /tmp/vault.zip
unzip /tmp/vault.zip -d /usr/local/bin
chmod 0750 /usr/local/bin/vault
chown vault:vault /usr/local/bin/vault

# Create Vault user
useradd -r -s /sbin/nologin -M vault

# Create directories
mkdir -p /etc/vault.d /opt/vault/data /var/log/vault
chown -R vault:vault /etc/vault.d /opt/vault/data /var/log/vault
chmod 0700 /etc/vault.d /opt/vault/data
chmod 0750 /var/log/vault

# Configure Vault
cat <<EOF > /etc/vault.d/vault.hcl
storage "file" {
  path = "/opt/vault/data"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_cert_file = "/etc/vault.d/vault-cert.pem"
  tls_key_file = "/etc/vault.d/vault-key.pem"
  tls_require_and_verify_client_cert = false
}
api_addr = "https://$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4):8200"
cluster_addr = "https://$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4):8201"
ui = true
EOF
chown vault:vault /etc/vault.d/vault.hcl
chmod 0600 /etc/vault.d/vault.hcl

# Generate TLS certificates
openssl genrsa -out /etc/vault.d/ca-key.pem 4096
openssl req -x509 -new -nodes -key /etc/vault.d/ca-key.pem -sha256 -days 365 -out /etc/vault.d/ca.pem -subj "/CN=Vault CA"
openssl genrsa -out /etc/vault.d/vault-key.pem 4096
openssl req -new -key /etc/vault.d/vault-key.pem -out /etc/vault.d/vault.csr -subj "/CN=${cluster_name}/O=Vault" -addext "subjectAltName=IP:$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4),DNS:localhost,IP:127.0.0.1"
openssl x509 -req -in /etc/vault.d/vault.csr -CA /etc/vault.d/ca.pem -CAkey /etc/vault.d/ca-key.pem -CAcreateserial -out /etc/vault.d/vault-cert.pem -days 365 -sha256 -extfile <(echo "subjectAltName=IP:$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4),DNS:localhost,IP:127.0.0.1")
chown vault:vault /etc/vault.d/*.pem /etc/vault.d/*.csr
chmod 0600 /etc/vault.d/*.pem /etc/vault.d/*.csr

# Configure Vault Nomad policy
cat <<EOF > /etc/vault.d/nomad-policy.hcl
path "secret/data/nomad/*" {
  capabilities = ["read", "list"]
}
path "auth/token/create/nomad-cluster" {
  capabilities = ["update"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
EOF
chown vault:vault /etc/vault.d/nomad-policy.hcl
chmod 0600 /etc/vault.d/nomad-policy.hcl

# Configure logrotate
cat <<EOF > /etc/logrotate.d/vault
/var/log/vault/vault.log {
  daily
  rotate 7
  compress
  delaycompress
  missingok
  notifempty
  create 0640 vault vault
  postrotate
    /bin/kill -HUP \$(pidof vault) 2> /dev/null || true
  endscript
}
EOF
chown root:root /etc/logrotate.d/vault
chmod 0644 /etc/logrotate.d/vault

# Configure systemd service
cat <<EOF > /etc/systemd/system/vault.service
[Unit]
Description=Vault
Documentation=https://www.vaultproject.io/docs
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/local/bin/vault server -config=/etc/vault.d/vault.hcl
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=5
User=vault
Group=vault
LimitNOFILE=65536
LimitNPROC=4096
StandardOutput=append:/var/log/vault/vault.log
StandardError=append:/var/log/vault/vault.log
Environment="VAULT_ADDR=https://0.0.0.0:8200"

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vault
systemctl start vault

# Initialize Vault
export VAULT_ADDR=https://$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4):8200
vault operator init -key-shares=1 -key-threshold=1 > /etc/vault.d/vault-init.txt
chown vault:vault /etc/vault.d/vault-init.txt
chmod 0600 /etc/vault.d/vault-init.txt

# Unseal Vault
VAULT_TOKEN=$(grep 'Initial Root Token' /etc/vault.d/vault-init.txt | awk '{print $NF}')
vault operator unseal $(grep 'Unseal Key' /etc/vault.d/vault-init.txt | awk '{print $NF}')

# Apply Nomad policy
vault policy write nomad-cluster /etc/vault.d/nomad-policy.hcl

# Configure Nomad role
vault auth enable -token=$${VAULT_TOKEN} approle
vault write auth/approle/role/nomad-cluster \
    token_policies="nomad-cluster" \
    token_ttl=1h \
    token_max_ttl=4h