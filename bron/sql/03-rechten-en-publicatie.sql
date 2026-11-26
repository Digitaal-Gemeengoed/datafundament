-- Draait één keer, na het schema. dlt_lezer mag alleen lezen; de publicatie
-- geeft elke wijziging in het schema brp door aan de logische replicatie (CDC),
-- ook van tabellen die later bijkomen.
REVOKE ALL ON DATABASE bron FROM PUBLIC;
GRANT CONNECT ON DATABASE bron TO dlt_lezer;
GRANT USAGE ON SCHEMA brp TO dlt_lezer;
GRANT SELECT ON ALL TABLES IN SCHEMA brp TO dlt_lezer;
ALTER DEFAULT PRIVILEGES IN SCHEMA brp GRANT SELECT ON TABLES TO dlt_lezer;

CREATE PUBLICATION datafundament FOR TABLES IN SCHEMA brp;
