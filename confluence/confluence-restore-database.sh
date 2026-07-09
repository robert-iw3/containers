#!/bin/bash
set -e

CONFLUENCE_CONTAINER=$(docker ps -aqf "name=confluence")
CONFLUENCE_BACKUPS_CONTAINER=$(docker ps -aqf "name=psql-backup")

echo "--> All available database backups:"

for entry in $(docker container exec -it $CONFLUENCE_BACKUPS_CONTAINER sh -c "ls /srv/confluence-postgres/backups/")
do
  echo "$entry"
done

echo "--> Copy and paste the backup name from the list above to restore database and press [ENTER]
--> Example: confluence-postgres-backup-YYYY-MM-DD_hh-mm.gz"
echo -n "--> "

read SELECTED_DATABASE_BACKUP

echo "--> $SELECTED_DATABASE_BACKUP was selected"

echo "--> Stopping service..."
docker stop $CONFLUENCE_CONTAINER

echo "--> Restoring database..."
docker exec -it $CONFLUENCE_BACKUPS_CONTAINER sh -c 'PGPASSWORD="$(echo $CONFLUENCE_DB_PASS)" dropdb -h postgres-confluence.io -p 5432 confluence -U confluence \
&& PGPASSWORD="$(echo $CONFLUENCE_DB_PASS)" createdb -h postgres-confluence.io -p 5432 confluence -U confluence \
&& PGPASSWORD="$(echo $CONFLUENCE_DB_PASS)" gunzip -c /srv/confluence-postgres/backups/'$SELECTED_DATABASE_BACKUP' | PGPASSWORD=$(echo $CONFLUENCE_DB_PASS) psql -h postgres-confluence.io -p 5432 confluence -U confluence'
echo "--> Database recovery completed..."

echo "--> Starting service..."
docker start $CONFLUENCE_CONTAINER
