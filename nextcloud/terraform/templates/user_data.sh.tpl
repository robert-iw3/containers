#!/bin/bash

# Create a directory to store the error log for the script
mkdir -p /var/log/user_data_script

# Redirect any error of the script to the output to the error log
exec 2>/var/log/user_data_script/errors.log

# Note AWS Nitro System-based instances (like C5, M5, R5, T3, and newer instance types) attach EBS volumes
# as NVMe block devices, which have a different naming convention compared to the traditional block device names.
# For instances that use the Xen hypervisor (including many earlier generation instance types),
# device names are in the format of /dev/xvdf through /dev/xvdp.
# For instances that use the Nitro hypervisor (including many newer generation instance types),
# device names are in the format of /dev/nvme1n1 through /dev/nvme26n1.

# This loop continues until the EBS volume is attached to the instance
# The instance checks for the existence of the  volume every 5 seconds
while [ ! -e "${ebs_volume_1_name}" ]; do
  echo "Waiting for "${ebs_volume_1_name}" to be attached"
  sleep 5
done

# Check if the EBS volume needs formatting
if ! file -s "${ebs_volume_1_name}" | grep -q filesystem; then
  sudo mkfs -t ext4 "${ebs_volume_1_name}"
fi

# Create the mount point directory
sudo mkdir -p "${ebs_volume_1_mount_point}"

# Mount the EBS volume
sudo mount "${ebs_volume_1_name}" "${ebs_volume_1_mount_point}"

# Configure automatic mount on reboot
echo "${ebs_volume_1_name} ${ebs_volume_1_mount_point} ext4 defaults,nofail 0 0" | sudo tee -a /etc/fstab > /dev/null

# This loop continues until the EBS volume is attached to the instance
# The instance checks for the existence of the  volume every 5 seconds
while [ ! -e "${ebs_volume_1_name}" ]; do
  echo "Waiting for "${ebs_volume_1_name}" to be attached"
  sleep 5
done

# Check if the EBS volume needs formatting
if ! file -s "${backup_ebs_volume_1_name}" | grep -q filesystem; then
  sudo mkfs -t ext4 "${backup_ebs_volume_1_name}"
fi

# Create the mount point directory
sudo mkdir -p "${backup_ebs_volume_1_mount_point}"

# Mount the EBS volume
sudo mount "${backup_ebs_volume_1_name}" "${backup_ebs_volume_1_mount_point}"

# Configure automatic mount on reboot
echo "${backup_ebs_volume_1_name} ${backup_ebs_volume_1_mount_point} ext4 defaults,nofail 0 0" | sudo tee -a /etc/fstab > /dev/null

# Create directories if it does not exist yet on a separate EBS volume
sudo mkdir -p "${backup_ebs_volume_1_mount_point}/nextcloud"

# Update the package lists for upgrades and new package installations
sudo apt-get update

# Install PostgreSQL client
sudo apt-get install -y curl openssh-server ca-certificates tzdata curl postgresql-client

# Create a backup if the source directory exists
if [ -d "${ebs_volume_1_mount_point}" ]; then
    tar -czvf "${backup_ebs_volume_1_mount_point}/nextcloud/$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_data_backup.tar.gz" -C "${ebs_volume_1_mount_point}" .
    echo "Backup created at ${backup_ebs_volume_1_mount_point}/nextcloud/$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_data_backup.tar.gz"

    RDS_ENDPOINT_NO_PORT=$(echo ${db_host_install} | sed 's/:5432//')
    PGPASSWORD=${db_password_install} pg_dump -U ${db_username_install} -h $RDS_ENDPOINT_NO_PORT -d ${db_name_install} > "${backup_ebs_volume_1_mount_point}/nextcloud/$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_db_backup.sql"
    echo "Database backup created at ${backup_ebs_volume_1_mount_point}/nextcloud/$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_db_backup.sql"
else
    echo "Directory to be backed up does not exist."
fi

# Define cron file
CRON_FILE="/tmp/nextcloud_backup_cron"

# Check if the backup cron job already exists
if [ -f "$CRON_FILE" ]; then
  grep -q "tar -czvf ${backup_ebs_volume_1_mount_point}/nextcloud/*_nextcloud_data_backup.tar.gz -C ${ebs_volume_1_mount_point}" "$CRON_FILE"
  if [[ $? -eq 0 ]]; then
    echo "Backup cron job already exists."
  else
    echo "Adding backup cron job to existing cron file..."
    echo "0 2 * * * tar -czvf ${backup_ebs_volume_1_mount_point}/nextcloud/\$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_data_backup.tar.gz -C ${ebs_volume_1_mount_point} ." >> "$CRON_FILE"
    echo "0 2 * * * PGPASSWORD=${db_password_install} pg_dump -U ${db_username_install} -h \$(echo ${db_host_install} | sed 's/:5432//') -d ${db_name_install} > ${backup_ebs_volume_1_mount_point}/nextcloud/\$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_db_backup.sql" >> "$CRON_FILE"
    crontab "$CRON_FILE"
  fi
else
  echo "Creating new cron file and adding backup cron job..."
  echo "0 2 * * * tar -czvf ${backup_ebs_volume_1_mount_point}/nextcloud/\$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_data_backup.tar.gz -C ${ebs_volume_1_mount_point} ." > "$CRON_FILE"
  echo "0 2 * * * PGPASSWORD=${db_password_install} pg_dump -U ${db_username_install} -h \$(echo ${db_host_install} | sed 's/:5432//') -d ${db_name_install} > ${backup_ebs_volume_1_mount_point}/nextcloud/\$(date +\%Y_\%m_\%d_\%H_\%M)_nextcloud_db_backup.sql" >> "$CRON_FILE"
  crontab "$CRON_FILE"
fi

# Check if the cleanup cron job already exists
grep -q "find ${backup_ebs_volume_1_mount_point}/nextcloud/*_nextcloud_data_backup.tar.gz -mtime +30 -delete" "$CRON_FILE"
if [[ $? -eq 0 ]]; then
  echo "Cleanup cron job already exists."
else
  echo "Adding cleanup cron job to existing cron file..."
  echo "0 3 * * * find ${backup_ebs_volume_1_mount_point}/nextcloud/*_nextcloud_data_backup.tar.gz -mtime +30 -delete" >> "$CRON_FILE"
  echo "0 3 * * * find ${backup_ebs_volume_1_mount_point}/nextcloud/*_nextcloud_db_backup.sql -mtime +30 -delete" >> "$CRON_FILE"
  crontab "$CRON_FILE"
fi

# Remove temporary cron file
rm "$CRON_FILE"

# Start the Docker Engine and Docker Compose installation
curl -fsSL https://get.docker.com | sudo sh

# Add the default user to the Docker group according to the distribution
usermod -aG docker ubuntu

# Activate Docker Swarm
sudo docker swarm init

# Write the rendered Nextcloud configuration to the nextcloud-docker-swarm.yml file
cat <<EOF > /opt/nextcloud-docker-swarm.yml
${nextcloud_config_file}
EOF

# Deploy Nextcloud stack in a Docker Swarm
sudo docker stack deploy -c /opt/nextcloud-docker-swarm.yml nextcloud
if [ $? -ne 0 ]; then exit 1; fi

# Remove all default template files (uncomment if needed)
# sudo rm -rf /mnt/nextcloud/core/skeleton/*
