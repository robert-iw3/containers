#!/bin/bash
# Restore a MariaDB dump produced by the backups sidecar or owncloud-backup.sh.
# Stops the app, drops/recreates the DB, restores, restarts.
set -euo pipefail

APP_CONTAINER=$(docker ps -aqf "name=owncloud-app")
BACKUPS_CONTAINER=$(docker ps -qf "name=owncloud-backups")

echo "--> Available database backups:"
docker exec "$BACKUPS_CONTAINER" sh -c "ls -1 /srv/backups/db/"

echo "--> Paste the backup file name to restore and press [ENTER]"
echo "--> Example: owncloud-mariadb-backup-YYYY-MM-DD_hh-mm.sql.gz"
echo -n "--> "
read -r SELECTED_BACKUP

echo "--> Stopping ownCloud..."
docker stop "$APP_CONTAINER"

echo "--> Restoring database from $SELECTED_BACKUP ..."
docker exec "$BACKUPS_CONTAINER" sh -c '
  set -e
  mariadb -h "$MYSQL_HOST" -u root -p"$MYSQL_ROOT_PASSWORD" \
    -e "DROP DATABASE IF EXISTS \`$MYSQL_DATABASE\`; CREATE DATABASE \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
  gunzip -c "/srv/backups/db/'"$SELECTED_BACKUP"'" \
    | mariadb -h "$MYSQL_HOST" -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"
'
echo "--> Database restore complete."

echo "--> Starting ownCloud..."
docker start "$APP_CONTAINER"
