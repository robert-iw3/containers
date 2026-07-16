#!/bin/bash
# Restore a /var/www/html archive produced by the backups sidecar or
# nextcloud-backup.sh into the nextcloud-data volume.
set -euo pipefail

APP_CONTAINER=$(docker ps -aqf "name=nextcloud-app")
CRON_CONTAINER=$(docker ps -aqf "name=nextcloud-cron")
BACKUPS_CONTAINER=$(docker ps -qf "name=nextcloud-backups")

echo "--> Available application data backups:"
docker exec "$BACKUPS_CONTAINER" sh -c "ls -1 /srv/backups/data/"

echo "--> Paste the backup file name to restore and press [ENTER]"
echo "--> Example: nextcloud-data-backup-YYYY-MM-DD_hh-mm.tar.gz"
echo -n "--> "
read -r SELECTED_BACKUP

echo "--> Stopping Nextcloud..."
docker stop "$APP_CONTAINER" "$CRON_CONTAINER"

# The data volume is mounted read-only in the backups container, so restore
# through a throwaway container that mounts it read-write.
echo "--> Restoring application data from $SELECTED_BACKUP ..."
docker run --rm \
  -v nextcloud_nextcloud-data:/var/www/html \
  -v nextcloud_nextcloud-data-backups:/srv/backups/data:ro \
  docker.io/alpine:3.21 \
  sh -c "rm -rf /var/www/html/* /var/www/html/..?* /var/www/html/.[!.]* 2>/dev/null; tar -xzpf /srv/backups/data/$SELECTED_BACKUP -C /var/www"
echo "--> Application data restore complete."

echo "--> Starting Nextcloud..."
docker start "$APP_CONTAINER" "$CRON_CONTAINER"
