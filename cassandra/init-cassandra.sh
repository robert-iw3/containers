#!/bin/bash

# Exit on error
set -e

# Only run on seeder node
if [ "$CASSANDRA_PASSWORD_SEEDER" != "yes" ]; then
  echo "Not a seeder node, skipping auth setup."
  exit 0
fi

# Wait for Cassandra to be ready
echo "Waiting for Cassandra to start..."
until cqlsh -u cassandra -p cassandra -e "describe keyspaces" > /dev/null 2>&1; do
  sleep 5
done

# Update cassandra user password
if [ -n "$CASSANDRA_PASSWORD" ]; then
  echo "Setting cassandra user password..."
  cqlsh -u cassandra -p cassandra -e "ALTER USER cassandra WITH PASSWORD '$CASSANDRA_PASSWORD'"
  echo "Password updated successfully."
else
  echo "CASSANDRA_PASSWORD not set, skipping password update."
fi