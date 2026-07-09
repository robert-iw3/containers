#!/bin/bash
set -e

# Initialize cluster metadata once. The redirect terminates the command cleanly
# (the previous version had a stray backslash before the redirect, which passed
# ">" and "logs/init-metadata.log" as arguments to the tool). Idempotent: a
# re-run against already-initialized metadata is treated as success.
bin/pulsar initialize-cluster-metadata \
  --cluster pulsar-cluster-1 \
  --zookeeper zoo1:2181 \
  --configuration-store zoo1:2181 \
  --web-service-url http://broker1:8080 \
  --broker-service-url pulsar://broker1:6650 \
  > logs/init-metadata.log 2>&1 || true

exec bin/bookkeeper bookie > logs/bookkeeper.log 2>&1
