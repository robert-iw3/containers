#!/bin/bash
# On-demand, application-consistent backup: puts ownCloud into maintenance
# mode (single-user mode), dumps MariaDB and archives /mnt/data, then
# re-enables service. The `backups` sidecar does the same on a schedule but
# without maintenance mode; use this script before upgrades or migrations.
set -euo pipefail

APP_CONTAINER=$(docker ps -qf "name=owncloud-app")
BACKUPS_CONTAINER=$(docker ps -qf "name=owncloud-backups")
STAMP=$(date +%Y-%m-%d_%H-%M)

if [ -z "$APP_CONTAINER" ] || [ -z "$BACKUPS_CONTAINER" ]; then
  echo "ERROR: owncloud-app / owncloud-backups containers not running" >&2
  exit 1
fi

cleanup() {
  echo "--> Leaving maintenance mode..."
  docker exec "$APP_CONTAINER" occ maintenance:mode --off || true
}
trap cleanup EXIT

echo "--> Entering maintenance mode..."
docker exec "$APP_CONTAINER" occ maintenance:mode --on

echo "--> Dumping database..."
docker exec "$BACKUPS_CONTAINER" sh -c \
  'mariadb-dump -h "$MYSQL_HOST" -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --events "$MYSQL_DATABASE" | gzip > "/srv/backups/db/owncloud-mariadb-backup-'"$STAMP"'.sql.gz"'

echo "--> Archiving files..."
docker exec "$BACKUPS_CONTAINER" sh -c \
  'tar -czf "/srv/backups/data/owncloud-files-backup-'"$STAMP"'.tar.gz" -C /mnt data'

echo "--> Backup complete:"
docker exec "$BACKUPS_CONTAINER" sh -c "ls -lh /srv/backups/db/*$STAMP* /srv/backups/data/*$STAMP*"
