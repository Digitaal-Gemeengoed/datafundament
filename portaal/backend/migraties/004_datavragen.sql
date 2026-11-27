-- df-portaal, migratie 004: elke datavraag vastleggen (DF-ADR-016).
-- Trino stuurt na elke query een gebeurtenis (HTTP event listener); de ontvanger
-- in het portaal legt die hier vast. Alleen toevoegen: wijzigen of verwijderen
-- weigert de database, ook voor de eigenaar.
SET search_path = beheer, public;

ALTER TABLE groepen DROP CONSTRAINT IF EXISTS groepen_rechten_check;
ALTER TABLE groepen ADD CONSTRAINT groepen_rechten_check CHECK (rechten <@ ARRAY[
  'accounts.view', 'accounts.manage', 'groups.view', 'groups.manage', 'audit.view', 'settings.view', 'settings.manage',
  'platform.view', 'dataproducten.view', 'toegang.aanvragen', 'toegang.beoordelen',
  'verwijderen.aanvragen', 'verwijderen.beoordelen', 'datavragen.view'
]::text[]);

CREATE TABLE datavragen (
  id            bigserial PRIMARY KEY,
  query_id      text NOT NULL UNIQUE,
  gebruiker     text NOT NULL,
  principal     text,
  bron          text,                  -- source: trino-jdbc, DBeaver, Trino CLI, ...
  client_adres  text,
  soort         text,                  -- SELECT, INSERT, DESCRIBE, ...
  status        text NOT NULL,         -- FINISHED, FAILED
  fout          text,
  sql           text NOT NULL,
  tabellen      jsonb NOT NULL DEFAULT '[]',  -- [{"tabel": "catalog.schema.tabel", "kolommen": [...]}]
  rijen         bigint,
  bytes         bigint,
  begin         timestamptz,
  einde         timestamptz,
  ontvangen     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX datavragen_einde ON datavragen (einde DESC);
CREATE INDEX datavragen_gebruiker ON datavragen (gebruiker, einde DESC);
CREATE INDEX datavragen_tabellen ON datavragen USING gin (tabellen jsonb_path_ops);

CREATE FUNCTION datavragen_vast() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'datavragen worden niet gewijzigd of verwijderd';
END $$;
CREATE TRIGGER datavragen_niet_wijzigen BEFORE UPDATE OR DELETE ON datavragen FOR EACH ROW EXECUTE FUNCTION datavragen_vast();
CREATE TRIGGER datavragen_niet_legen BEFORE TRUNCATE ON datavragen FOR EACH STATEMENT EXECUTE FUNCTION datavragen_vast();

GRANT SELECT, INSERT ON datavragen TO df_portaal_app;
GRANT USAGE ON SEQUENCE datavragen_id_seq TO df_portaal_app;
