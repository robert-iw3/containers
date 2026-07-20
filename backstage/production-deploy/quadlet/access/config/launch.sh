#!/bin/sh
# Initialize the boundary database on first boot (idempotent), then serve.
set -e

out=$(boundary database init -config /cfg/boundary.hcl 2>&1); rc=$?
echo "$out"
if [ $rc -ne 0 ] && ! echo "$out" | grep -qi 'already.*initialized'; then
  exit $rc
fi
exec boundary server -config /cfg/boundary.hcl
