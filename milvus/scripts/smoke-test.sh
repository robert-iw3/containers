#!/usr/bin/env bash
# Smoke test for the Milvus stack: health endpoints, authentication
# (both that good creds work and that bad creds are rejected), and a
# round-trip through the RESTful v2 API.
set -euo pipefail

cd "$(dirname "$0")/.."

RUNTIME="${RUNTIME:-podman}"
BASE=http://127.0.0.1:19530/v2/vectordb

[ -s .env ] || { echo "FAIL: milvus/.env missing — run ./scripts/bootstrap-env.sh"; exit 1; }
# shellcheck disable=SC1091
. ./.env

PASS=0
FAIL=0
check() { # check <description> <expected> <actual>
  if [ "$3" = "$2" ]; then
    PASS=$((PASS + 1)); printf '  PASS  %-52s %s\n' "$1" "$3"
  else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-52s got %s want %s\n' "$1" "$3" "$2"
  fi
}

echo "==> waiting for milvus health endpoint"
for i in $(seq 1 90); do
  if curl -sf http://127.0.0.1:9091/healthz >/dev/null 2>&1; then break; fi
  [ "$i" = 90 ] && { echo "FAIL: /healthz never responded"; exit 1; }
  sleep 2
done
echo "    /healthz OK"

echo "==> waiting for one-shot root-password rotation (milvus-init)"
for i in $(seq 1 60); do
  state=$("$RUNTIME" inspect --format '{{.State.Status}} {{.State.ExitCode}}' milvus-init 2>/dev/null || echo missing)
  case "$state" in
    "exited 0") break ;;
    exited*) echo "FAIL: milvus-init exited non-zero"; "$RUNTIME" logs milvus-init | tail -5; exit 1 ;;
  esac
  [ "$i" = 60 ] && { echo "FAIL: milvus-init never finished ($state)"; exit 1; }
  sleep 2
done
echo "    root password rotated"

echo "==> API checks"
authed() { # authed <user:pass> <path> <json>
  curl -s -X POST "$BASE/$2" -H "Authorization: Bearer $1" \
    -H 'Content-Type: application/json' -d "$3" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("code"))' 2>/dev/null || echo err
}

check "list databases with rotated root creds" 0 \
  "$(authed "root:$MILVUS_ROOT_PASSWORD" databases/list '{}')"
check "factory-default root creds rejected" 1800 \
  "$(authed "root:Milvus" databases/list '{}')"
check "no Authorization header rejected" 1800 \
  "$(curl -s -X POST "$BASE/databases/list" -H 'Content-Type: application/json' -d '{}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin).get("code"))')"

smoke_col=smoke_$$
create=$(authed "root:$MILVUS_ROOT_PASSWORD" collections/create \
  "{\"collectionName\":\"$smoke_col\",\"dimension\":8}")
check "create collection" 0 "$create"
insert=$(authed "root:$MILVUS_ROOT_PASSWORD" entities/insert \
  "{\"collectionName\":\"$smoke_col\",\"data\":[{\"id\":1,\"vector\":[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8]}]}")
check "insert entity" 0 "$insert"
search=$(authed "root:$MILVUS_ROOT_PASSWORD" entities/search \
  "{\"collectionName\":\"$smoke_col\",\"data\":[[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8]],\"limit\":1}")
check "vector search" 0 "$search"
drop=$(authed "root:$MILVUS_ROOT_PASSWORD" collections/drop \
  "{\"collectionName\":\"$smoke_col\"}")
check "drop collection" 0 "$drop"

echo "==> infrastructure checks"
check "etcd healthy" healthy \
  "$("$RUNTIME" inspect --format '{{.State.Health.Status}}' milvus-etcd)"
check "minio healthy" healthy \
  "$("$RUNTIME" inspect --format '{{.State.Health.Status}}' milvus-minio)"
check "attu UI reachable" 200 \
  "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/)"

echo
echo "smoke test: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
