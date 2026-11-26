#!/usr/bin/env bash
# Draait één keer, bij het eerste starten van een lege database.
# De leesgebruiker voor dlt op dfc: lezen en logische replicatie, verder niets.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v wachtwoord="$DLT_WACHTWOORD" <<'EOSQL'
CREATE ROLE dlt_lezer LOGIN REPLICATION PASSWORD :'wachtwoord';
EOSQL
