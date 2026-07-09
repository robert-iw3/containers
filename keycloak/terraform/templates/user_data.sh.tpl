#!/bin/bash

# Create a directory to store the error log for the script
mkdir -p /var/log/user_data_script

# Redirect any error of the script to the output to the error log
exec 2>/var/log/user_data_script/errors.log

# Update the package lists for upgrades and new package installations
sudo apt-get update

# Install PostgreSQL client
sudo apt-get install -y curl openssh-server ca-certificates tzdata curl postgresql-client

# Start the Docker Engine and Docker Compose installation
curl -fsSL https://get.docker.com | sudo sh

# Add the default user to the Docker group according to the distribution
usermod -aG docker ubuntu

# Activate Docker Swarm
sudo docker swarm init

# Write the rendered Keycloak configuration to the keycloak-docker-swarm.yml file
cat <<EOF > /opt/keycloak-docker-swarm.yml
${keycloak_config_file}
EOF

# Set database host for Keycloak
sudo sed -i '/KC_DB_URL_HOST/s/:5432//' /opt/keycloak-docker-swarm.yml

# Deploy Keycloak stack in a Docker Swarm
sudo docker stack deploy -c /opt/keycloak-docker-swarm.yml keycloak
if [ $? -ne 0 ]; then exit 1; fi
