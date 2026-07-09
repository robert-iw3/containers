#!/bin/bash
set -e

NEXTCLOUD_CONTAINER=$(docker ps -aqf "name=nextcloud")
NEXTCLOUD_BACKUPS_CONTAINER=$(docker ps -aqf "name=postgres_backup")

echo "--> All available database backups:"

for entry in $(docker container exec -it $NEXTCLOUD_BACKUPS_CONTAINER sh -c "ls /srv/nextcloud-postgres/backups/")
do
  echo "$entry"
done

echo "--> Copy and paste the backup name from the list above to restore database and press [ENTER]
--> Example: nextcloud-postgres-backup-YYYY-MM-DD_hh-mm.gz"
echo -n "--> "

read SELECTED_DATABASE_BACKUP

echo "--> $SELECTED_DATABASE_BACKUP was selected"

echo "--> Stopping service..."
docker stop $NEXTCLOUD_CONTAINER

echo "--> Restoring database..."
docker exec -it $NEXTCLOUD_BACKUPS_CONTAINER sh -c 'PGPASSWORD="$(echo $NEXTCLOUD_DB_PASS)" dropdb -h postgres-nextcloud.io -p 5432 nextcloud -U nextcloud \
&& PGPASSWORD="$(echo $NEXTCLOUD_DB_PASS)" createdb -h postgres-nextcloud.io -p 5432 nextcloud -U nextcloud \
&& PGPASSWORD="$(echo $NEXTCLOUD_DB_PASS)" gunzip -c /srv/nextcloud-postgres/backups/'$SELECTED_DATABASE_BACKUP' | PGPASSWORD=$(echo $NEXTCLOUD_DB_PASS) psql -h postgres-nextcloud.io -p 5432 nextcloud -U nextcloud'
echo "--> Database recovery completed..."

echo "--> Starting service..."
docker start $NEXTCLOUD_CONTAINER
