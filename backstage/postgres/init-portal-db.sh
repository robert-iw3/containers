#!/bin/sh
# Creates the portal's database role. The bootstrap password is replaced by
# Vault the moment the static role is registered (vault-setup.sh), so it
# never has to be shared with the portal.
set -e

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<EOSQL
CREATE ROLE backstage LOGIN CREATEDB PASSWORD '${BACKSTAGE_DB_BOOTSTRAP_PASSWORD}';
CREATE ROLE keycloak LOGIN PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE DATABASE keycloak OWNER keycloak;
EOSQL
