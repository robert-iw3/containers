#!/bin/bash
# Install dependencies and monitoring tools
apt-get update
apt-get install -y prometheus prometheus-node-exporter grafana logrotate unzip awscli

# Install Podman
apt-get install -y podman
systemctl enable podman.socket
systemctl start podman.socket

# Retrieve Grafana admin password from Secrets Manager
export AWS_REGION=${aws_region}
grafana_admin_password=$(aws secretsmanager get-secret-value --secret-id ${secrets_arn} --query SecretString --output text | jq -r '.grafana_admin_password')

# Configure Prometheus
mkdir -p /etc/prometheus
echo "${prometheus_config}" | base64 -d > /etc/prometheus/prometheus.yml
chown prometheus:prometheus /etc/prometheus/prometheus.yml
chmod 0600 /etc/prometheus/prometheus.yml
systemctl enable prometheus
systemctl start prometheus

# Configure Grafana
grafana-cli --homepath "/usr/share/grafana" admin reset-admin-password "$grafana_admin_password"
systemctl enable grafana-server
systemctl start grafana-server

# Configure logrotate for Prometheus and Grafana
cat <<EOF > /etc/logrotate.d/monitoring
/var/log/prometheus/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 prometheus prometheus
    postrotate
        systemctl reload prometheus
    endscript
}

/var/log/grafana/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 grafana grafana
    postrotate
        systemctl reload grafana-server
    endscript
}
EOF

# Verify logrotate configuration
logrotate -f /etc/logrotate.d/monitoring

# Clean up temporary files
rm -rf /tmp/*