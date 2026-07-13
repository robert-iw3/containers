#!/usr/bin/env bash
# Apply the declarative schema to a running Cassandra cluster (idempotent).
#   ./scripts/apply_schema.sh [contact-host] [schema.cql]
# Uses a one-off cqlsh container on the compose network (no host cqlsh needed).
set -euo pipefail
HOST="${1:-cassandra1}"
SCHEMA="${2:-$(dirname "$0")/../schema/schema.cql}"
RUNTIME="$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)"
NET="$($RUNTIME network ls --format '{{.Name}}' | grep -iE 'cassandra' | head -1)"
"$RUNTIME" run --rm --network "$NET" -v "$(realpath "$SCHEMA")":/schema.cql:ro \
  docker.io/library/cassandra:5.0 cqlsh "$HOST" -f /schema.cql
echo "schema applied to $HOST"
