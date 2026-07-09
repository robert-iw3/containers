#!/bin/bash

set -e

BACKUP_FILE=$1
POSTGRES_HOST=${POSTGRESQL_IPv4:-172.28.0.2}
POSTGRES_USER=${POSTGRESQL_USERNAME:-bitbucket_user}
POSTGRES_DB=${POSTGRESQL_DATABASE:-bitbucket}
POSTGRES_PASSWORD=$(cat secrets/postgresql_password)

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

docker exec -e PGPASSWORD=$POSTGRES_PASSWORD postgres-bitbucket \
  bash -c "zstd -d -c /srv/bitbucket-postgres/backups/$BACKUP_FILE | psql -U $POSTGRES_USER -d $POSTGRES_DB"

# Validate restored data
TABLE_COUNT=$(docker exec -e PGPASSWORD=$POSTGRES_PASSWORD postgres-bitbucket \
  psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
if [ "$TABLE_COUNT" -gt 0 ]; then
  echo "Restoration successful: $TABLE_COUNT tables found in restored database."
else
  echo "Restoration failed: No tables found in restored database."
  exit 1
fi