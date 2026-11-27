-- df-portaal, migratie 005: Trino via Keycloak, met rechten per kolom (DF-ADR-017).
--
-- Een toekenning geldt voor een dataproduct. Kolommen die in dbt een label
-- persoonsgegeven of bijzonder hebben, zijn gemaskeerd, tenzij de beoordelaar
-- bij het toekennen 'met persoonsgegevens' aanvinkt. Het recht lagen.lezen geeft
-- leestoegang tot alle lagen (uniform, ruw): voor data-engineers.
SET search_path = beheer, public;

ALTER TABLE groepen DROP CONSTRAINT IF EXISTS groepen_rechten_check;
ALTER TABLE groepen ADD CONSTRAINT groepen_rechten_check CHECK (rechten <@ ARRAY[
  'accounts.view', 'accounts.manage', 'groups.view', 'groups.manage', 'audit.view', 'settings.view', 'settings.manage',
  'platform.view', 'dataproducten.view', 'toegang.aanvragen', 'toegang.beoordelen',
  'verwijderen.aanvragen', 'verwijderen.beoordelen', 'datavragen.view', 'lagen.lezen'
]::text[]);

ALTER TABLE toegangsaanvragen ADD COLUMN met_persoonsgegevens boolean NOT NULL DEFAULT false;

-- Het vinkje zet de beoordelaar bij het besluit; daarna ligt het vast.
CREATE FUNCTION persoonsgegevens_vast() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'aangevraagd' AND NEW.met_persoonsgegevens IS DISTINCT FROM OLD.met_persoonsgegevens THEN
    RAISE EXCEPTION 'met persoonsgegevens ligt vast na het besluit';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER toegangsaanvragen_persoonsgegevens BEFORE UPDATE ON toegangsaanvragen
  FOR EACH ROW EXECUTE FUNCTION persoonsgegevens_vast();

GRANT UPDATE (met_persoonsgegevens) ON toegangsaanvragen TO df_portaal_app;
