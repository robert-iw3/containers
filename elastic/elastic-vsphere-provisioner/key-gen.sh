# version
echo "ELASTIC_VERSION=9.2.0" >> .env
# system passwords
echo "ELASTIC_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "LOGSTASH_INTERNAL_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "KIBANA_SYSTEM_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "METRICBEAT_INTERNAL_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "FILEBEAT_INTERNAL_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "HEARTBEAT_INTERNAL_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "MONITORING_INTERNAL_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "BEATS_SYSTEM_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "ENT_SEARCH_DEFAULT_PASSWORD=$(openssl rand -hex 36 | tr -d '\n')" >> .env
echo "APM_SERVER_TOKEN=$(openssl rand -hex 36 | tr -d '\n')" >> .env
# kibana encryption keys
echo "xpack.security.encryptionKey: $(openssl rand -hex 48 | tr -d '\n')" >> kibana/config/kibana.yml
echo "xpack.reporting.encryptionKey: $(openssl rand -hex 48 | tr -d '\n')" >> kibana/config/kibana.yml
echo "xpack.encryptedSavedObjects.encryptionKey: $(openssl rand -hex 48 | tr -d '\n')" >> kibana/config/kibana.yml
# vmware
echo "VCENTER_HOST=vcenter.example.com" >> .env
echo "VCENTER_USER=admin@vsphere.local" >> .env
echo "VCENTER_PASSWORD=your_password" >> .env
echo "DATACENTER=Datacenter" >> .env
echo "CLUSTER=Cluster" >> .env
echo "DATASTORE=datastore1" >> .env
echo "TEMPLATE=ubuntu-template" >> .env
echo "SSH_USER=ubuntu" >> .env
echo "SSH_KEY=~/.ssh/id_rsa" >> .env