#!/bin/sh
# Production first-boot roles/databases. The portal's bootstrap password is
# replaced by Vault the moment the static role is registered; keycloak and
# boundary get their own databases on this shared DBMS.
set -e

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<EOSQL
CREATE ROLE backstage LOGIN CREATEDB PASSWORD '${BACKSTAGE_DB_BOOTSTRAP_PASSWORD}';
CREATE ROLE keycloak LOGIN PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE DATABASE keycloak OWNER keycloak;
CREATE ROLE boundary LOGIN PASSWORD '${BOUNDARY_DB_PASSWORD}';
CREATE DATABASE boundary OWNER boundary;
EOSQL
