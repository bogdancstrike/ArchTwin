#!/bin/sh
# First-start initialisation of the shared PostgreSQL (runs once, from docker-entrypoint-initdb.d).
# - databases for third parties (temporal DBs are created by temporal auto-setup)
# - archtwin_app: the role the API and worker use. Not the owner and NOBYPASSRLS, so row-level security applies
#   (defense in depth, ADR-0002, AT-PROJECT_BOUNDARIES). Migrations run as the owner role.
# - archtwin_catalog_ro: read-only role for the PostgreSQL catalog connector's self-twin demo.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE DATABASE keycloak;
CREATE DATABASE litellm;
CREATE DATABASE langfuse;
CREATE ROLE archtwin_app LOGIN PASSWORD '${ARCHTWIN_APP_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE archtwin_catalog_ro LOGIN PASSWORD '${ARCHTWIN_APP_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO archtwin_app, archtwin_catalog_ro;
GRANT USAGE ON SCHEMA public TO archtwin_app, archtwin_catalog_ro;
ALTER ROLE archtwin_catalog_ro SET default_transaction_read_only = on;
SQL
