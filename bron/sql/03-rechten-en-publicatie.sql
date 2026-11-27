-- Draait één keer, na het schema. dlt_lezer mag alleen lezen. De publicaties
-- voor de logische replicatie (CDC) zet werkbank/publicaties.py, na het laden:
-- per tabel met de kolommen die mee mogen (DF-ADR-006).
REVOKE ALL ON DATABASE bron FROM PUBLIC;
GRANT CONNECT ON DATABASE bron TO dlt_lezer;
GRANT USAGE ON SCHEMA brp TO dlt_lezer;
GRANT SELECT ON ALL TABLES IN SCHEMA brp TO dlt_lezer;
ALTER DEFAULT PRIVILEGES IN SCHEMA brp GRANT SELECT ON TABLES TO dlt_lezer;

