#!/bin/bash

TARGET_DIR="/opt/hyperdx"
BACKUP_DIR="/backups/hyperdx_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

docker compose -f "$TARGET_DIR/docker-compose.yml" down

rsync -av "$TARGET_DIR/.volumes/ch_data/" "$BACKUP_DIR/ch_data/"
rsync -av "$TARGET_DIR/.volumes/db/" "$BACKUP_DIR/db/"
rsync -av "$TARGET_DIR/.volumes/ch_logs/" "$BACKUP_DIR/ch_logs/"

docker compose -f "$TARGET_DIR/docker-compose.yml" up -d

echo "Backup created at $BACKUP_DIR"