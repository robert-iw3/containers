#!/bin/bash
set -e

JIRA_CONTAINER=$(docker ps -aqf "name=jira")
JIRA_BACKUPS_CONTAINER=$(docker ps -aqf "name=psql-backup")

echo "--> All available database backups:"

for entry in $(docker container exec -it $JIRA_BACKUPS_CONTAINER sh -c "ls /srv/jira-postgres/backups/")
do
  echo "$entry"
done

echo "--> Copy and paste the backup name from the list above to restore database and press [ENTER]
--> Example: jira-postgres-backup-YYYY-MM-DD_hh-mm.gz"
echo -n "--> "

read SELECTED_DATABASE_BACKUP

echo "--> $SELECTED_DATABASE_BACKUP was selected"

echo "--> Stopping service..."
docker stop $JIRA_CONTAINER

echo "--> Restoring database..."
docker exec -it $JIRA_BACKUPS_CONTAINER sh -c 'PGPASSWORD="$(echo $JIRA_DB_PASS)" dropdb -h postgres-jira.io -p 5432 jira -U jira \
&& PGPASSWORD="$(echo $JIRA_DB_PASS)" createdb -h postgres-jira.io -p 5432 jira -U jira \
&& PGPASSWORD="$(echo $JIRA_DB_PASS)" gunzip -c /srv/jira-postgres/backups/'$SELECTED_DATABASE_BACKUP' | PGPASSWORD=$(echo $JIRA_DB_PASS) psql -h postgres-jira.io -p 5432 jira -U jira'
echo "--> Database recovery completed..."

echo "--> Starting service..."
docker start $JIRA_CONTAINER
