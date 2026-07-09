#!/bin/bash

# Generate secure connection JSON
cat << EOF > postgres_connection.json
{
    "conn_type": "postgres",
    "host": "postgres",
    "port": 5432,
    "schema": "airflow",
    "login": "airflow",
    "password": "${POSTGRES_PASSWORD}",
    "extra": { "sslmode": "require" }
}
EOF

# List existing connections
airflow connections list

# Add connection using secure JSON file
airflow connections add 'postgres_default' --conn-json "$(cat postgres_connection.json)"

# Verify connection
airflow connections list

# Clean up
rm postgres_connection.json