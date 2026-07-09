#!/bin/bash

# Create admin user with secure password from environment variable
airflow users create \
    --username "${_AIRFLOW_WWW_USER_USERNAME:-airflow}" \
    --firstname Airflow \
    --lastname Admin \
    --role Admin \
    --email airflow@noreply.com \
    --password "${_AIRFLOW_WWW_USER_PASSWORD:-airflow}"