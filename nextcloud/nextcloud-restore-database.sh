#!/bin/bash
# Restore a PostgreSQL dump produced by the backups sidecar or
# nextcloud-backup.sh. Stops the app, drops/recreates the DB, restores,
# restarts. Uses the superuser connection from the backups container env.
set -euo pipefail

APP_CONTAINER=$(docker ps -aqf "name=nextcloud-app")
CRON_CONTAINER=$(docker ps -aqf "name=nextcloud-cron")
BACKUPS_CONTAINER=$(docker ps -qf "name=nextcloud-backups")

echo "--> Available database backups:"
docker exec "$BACKUPS_CONTAINER" sh -c "ls -1 /srv/backups/db/"

echo "--> Paste the backup file name to restore and press [ENTER]"
echo "--> Example: nextcloud-postgres-backup-YYYY-MM-DD_hh-mm.sql.gz"
echo -n "--> "
read -r SELECTED_BACKUP

echo "--> Stopping Nextcloud..."
docker stop "$APP_CONTAINER" "$CRON_CONTAINER"

echo "--> Restoring database from $SELECTED_BACKUP ..."
docker exec "$BACKUPS_CONTAINER" sh -c '
  set -e
  psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\";" \
    -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"
  gunzip -c "/srv/backups/db/'"$SELECTED_BACKUP"'" \
    | psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB"
'
echo "--> Database restore complete."

echo "--> Starting Nextcloud..."
docker start "$APP_CONTAINER" "$CRON_CONTAINER"
