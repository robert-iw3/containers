#!/bin/bash
# Restore an /mnt/data archive produced by the backups sidecar or
# owncloud-backup.sh into the owncloud-files volume.
set -euo pipefail

APP_CONTAINER=$(docker ps -aqf "name=owncloud-app")
BACKUPS_CONTAINER=$(docker ps -qf "name=owncloud-backups")

echo "--> Available file backups:"
docker exec "$BACKUPS_CONTAINER" sh -c "ls -1 /srv/backups/data/"

echo "--> Paste the backup file name to restore and press [ENTER]"
echo "--> Example: owncloud-files-backup-YYYY-MM-DD_hh-mm.tar.gz"
echo -n "--> "
read -r SELECTED_BACKUP

echo "--> Stopping ownCloud..."
docker stop "$APP_CONTAINER"

# The files volume is mounted read-only in the backups container, so restore
# through a throwaway container that mounts it read-write.
echo "--> Restoring files from $SELECTED_BACKUP ..."
docker run --rm \
  -v owncloud_owncloud-files:/mnt/data \
  -v owncloud_owncloud-data-backups:/srv/backups/data:ro \
  docker.io/alpine:3.21 \
  sh -c "rm -rf /mnt/data/* /mnt/data/..?* /mnt/data/.[!.]* 2>/dev/null; tar -xzpf /srv/backups/data/$SELECTED_BACKUP -C /mnt"
echo "--> Files restore complete."

echo "--> Starting ownCloud..."
docker start "$APP_CONTAINER"
