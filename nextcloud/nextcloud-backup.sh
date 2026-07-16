#!/bin/bash
# On-demand, application-consistent backup: puts Nextcloud into maintenance
# mode, dumps PostgreSQL and archives /var/www/html, then re-enables service.
# The `backups` sidecar does the same on a schedule but without maintenance
# mode; use this script before upgrades or migrations.
set -euo pipefail

APP_CONTAINER=$(docker ps -qf "name=nextcloud-app")
BACKUPS_CONTAINER=$(docker ps -qf "name=nextcloud-backups")
STAMP=$(date +%Y-%m-%d_%H-%M)

if [ -z "$APP_CONTAINER" ] || [ -z "$BACKUPS_CONTAINER" ]; then
  echo "ERROR: nextcloud-app / nextcloud-backups containers not running" >&2
  exit 1
fi

cleanup() {
  echo "--> Leaving maintenance mode..."
  docker exec -u www-data "$APP_CONTAINER" php occ maintenance:mode --off || true
}
trap cleanup EXIT

echo "--> Entering maintenance mode..."
docker exec -u www-data "$APP_CONTAINER" php occ maintenance:mode --on

echo "--> Dumping database..."
docker exec "$BACKUPS_CONTAINER" sh -c \
  'pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "/srv/backups/db/nextcloud-postgres-backup-'"$STAMP"'.sql.gz"'

echo "--> Archiving application data..."
docker exec "$BACKUPS_CONTAINER" sh -c \
  'tar -czf "/srv/backups/data/nextcloud-data-backup-'"$STAMP"'.tar.gz" -C /var/www html'

echo "--> Backup complete:"
docker exec "$BACKUPS_CONTAINER" sh -c "ls -lh /srv/backups/db/*$STAMP* /srv/backups/data/*$STAMP*"
