#!/usr/bin/env bash
# cloud-init: install ${product} ${product_version} from releases.hashicorp.com
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
for i in 1 2 3; do apt-get update -y && break || sleep 10; done
apt-get install -y unzip curl jq

cd /tmp
curl -fsSLO "https://releases.hashicorp.com/${product}/${product_version}/${product}_${product_version}_linux_amd64.zip"
curl -fsSLO "https://releases.hashicorp.com/${product}/${product_version}/${product}_${product_version}_SHA256SUMS"
grep "${product}_${product_version}_linux_amd64.zip" "${product}_${product_version}_SHA256SUMS" | sha256sum -c -
unzip -o "${product}_${product_version}_linux_amd64.zip" ${product} -d /usr/local/bin
chmod 0755 "/usr/local/bin/${product}"
rm -f "${product}_${product_version}_linux_amd64.zip" "${product}_${product_version}_SHA256SUMS"

useradd --system --home "/etc/${product}.d" --shell /bin/false "${product}" 2>/dev/null || true
mkdir -p "/etc/${product}.d" "/opt/${product}/data"

PRIVATE_IP="$(hostname -I | awk '{print $1}')"
NODE_HOSTNAME="$(hostname -s)"

%{ for path, content in extra_files ~}
mkdir -p "$(dirname '${path}')"
cat > '${path}' <<'TF_EOF'
${content}
TF_EOF
%{ endfor ~}

cat > "/etc/${product}.d/server.hcl" <<'TF_EOF'
${config}
TF_EOF
sed -i "s|__PRIVATE_IP__|$${PRIVATE_IP}|g; s|__HOSTNAME__|$${NODE_HOSTNAME}|g" "/etc/${product}.d/server.hcl"

%{ if env_content != "" ~}
cat > "/etc/${product}.d/${product}.env" <<'TF_EOF'
${env_content}
TF_EOF
chmod 0600 "/etc/${product}.d/${product}.env"
%{ endif ~}

chown -R "${product}:${product}" "/etc/${product}.d" "/opt/${product}"
chmod 0640 "/etc/${product}.d/server.hcl"

%{ if extra_setup != "" ~}
${extra_setup}
%{ endif ~}

cat > "/etc/systemd/system/${product}.service" <<TF_EOF
[Unit]
Description=HashiCorp ${product}
Documentation=https://developer.hashicorp.com/${product}/docs
Requires=network-online.target
After=network-online.target
ConditionFileNotEmpty=/etc/${product}.d/server.hcl

[Service]
Type=notify
User=${product}
Group=${product}
%{ if env_content != "" ~}
EnvironmentFile=-/etc/${product}.d/${product}.env
%{ endif ~}
ExecStart=${exec_start}
ExecReload=/bin/kill --signal HUP \$MAINPID
KillMode=process
KillSignal=SIGINT
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
TF_EOF

systemctl daemon-reload
systemctl enable --now "${product}.service"
