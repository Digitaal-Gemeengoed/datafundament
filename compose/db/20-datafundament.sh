#!/usr/bin/env bash
# Draait één keer, bij het eerste starten van een lege database (na het script van PostGIS).
# Een eigen rol en database per onderdeel; de afnemers lezen het datawarehouse
# alleen via Trino, met de rol dwh_lezer (DF-ADR-008).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v lk="$LK_DB_WACHTWOORD" -v dg="$DAGSTER_DB_WACHTWOORD" \
  -v dws="$DWH_SCHRIJVER_WACHTWOORD" -v dwl="$DWH_LEZER_WACHTWOORD" <<'EOSQL'
CREATE ROLE lakekeeper LOGIN PASSWORD :'lk';
CREATE DATABASE lakekeeper OWNER lakekeeper;

CREATE ROLE dagster LOGIN PASSWORD :'dg';
CREATE DATABASE dagster OWNER dagster;

-- Het datawarehouse: dataproducten met PostGIS (DF-ADR-001).
CREATE ROLE dwh_schrijver LOGIN PASSWORD :'dws';
CREATE ROLE dwh_lezer LOGIN PASSWORD :'dwl';
CREATE DATABASE dwh OWNER dwh_schrijver;
REVOKE ALL ON DATABASE dwh FROM PUBLIC;
GRANT CONNECT ON DATABASE dwh TO dwh_schrijver, dwh_lezer;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dwh <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA dataproduct AUTHORIZATION dwh_schrijver;
GRANT USAGE ON SCHEMA dataproduct TO dwh_lezer;
ALTER DEFAULT PRIVILEGES FOR ROLE dwh_schrijver IN SCHEMA dataproduct GRANT SELECT ON TABLES TO dwh_lezer;
EOSQL
