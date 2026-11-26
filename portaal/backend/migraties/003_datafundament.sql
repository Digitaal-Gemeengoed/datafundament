-- df-portaal, migratie 003: het Datafundament. Rechten voor platform,
-- dataproducten, toegangsaanvragen en verwijderverzoeken (DF-ADR-013, DF-ADR-015).
-- Aanvragen en verzoeken worden nooit verwijderd: de app-rol mag alleen
-- toevoegen en de status bijwerken. Iemand beoordeelt nooit zijn eigen aanvraag.
SET search_path = beheer, public;

ALTER TABLE groepen DROP CONSTRAINT IF EXISTS groepen_rechten_check;
ALTER TABLE groepen ADD CONSTRAINT groepen_rechten_check CHECK (rechten <@ ARRAY[
  'accounts.view', 'accounts.manage', 'groups.view', 'groups.manage', 'audit.view', 'settings.view', 'settings.manage',
  'platform.view', 'dataproducten.view', 'toegang.aanvragen', 'toegang.beoordelen',
  'verwijderen.aanvragen', 'verwijderen.beoordelen'
]::text[]);

-- Toegang tot een dataproduct. Een toekenning wordt later een regel in Trino
-- (via Git, DF-ADR-008); tot Trino via Keycloak inlogt, is dit het register.
CREATE TABLE toegangsaanvragen (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataproduct   text NOT NULL CHECK (dataproduct ~ '^[a-z0-9_]+(/[a-z0-9_]+){1,3}$'),
  aanvrager     uuid NOT NULL REFERENCES accounts (id),
  doel          text NOT NULL CHECK (length(doel) BETWEEN 10 AND 2000),
  grondslag     text NOT NULL CHECK (length(grondslag) BETWEEN 3 AND 500),
  gewenst_tot   date,
  status        text NOT NULL DEFAULT 'aangevraagd' CHECK (status IN ('aangevraagd', 'toegekend', 'afgewezen', 'ingetrokken')),
  beoordelaar   uuid REFERENCES accounts (id),
  beoordeeld    timestamptz,
  toelichting   text CHECK (toelichting IS NULL OR length(toelichting) BETWEEN 5 AND 2000),
  aangemaakt    timestamptz NOT NULL DEFAULT now(),
  CHECK (beoordelaar IS NULL OR beoordelaar <> aanvrager),
  CHECK ((status = 'aangevraagd') = (beoordeeld IS NULL))
);
CREATE INDEX toegangsaanvragen_open ON toegangsaanvragen (aangemaakt) WHERE status = 'aangevraagd';

-- Een verzoek om de gegevens van een persoon uit het lakehouse te verwijderen
-- (AVG art. 17, of een verlopen bewaartermijn). Het BSN staat hier nooit: alleen
-- de HMAC met de sleutel van de kluis (dezelfde als bij de ingestie) en de
-- laatste drie cijfers, om het verzoek te herkennen.
CREATE TABLE verwijderverzoeken (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bsn_hmac      bytea NOT NULL CHECK (length(bsn_hmac) = 32),
  bsn_einde     text NOT NULL CHECK (bsn_einde ~ '^[0-9]{3}$'),
  grondslag     text NOT NULL CHECK (grondslag IN ('avg-art17', 'bewaartermijn', 'onrechtmatig', 'overig')),
  reden         text NOT NULL CHECK (length(reden) BETWEEN 10 AND 2000),
  aanvrager     uuid NOT NULL REFERENCES accounts (id),
  aangemaakt    timestamptz NOT NULL DEFAULT now(),
  status        text NOT NULL DEFAULT 'aangevraagd'
                CHECK (status IN ('aangevraagd', 'afgewezen', 'in-uitvoering', 'uitgevoerd', 'mislukt')),
  beoordelaar   uuid REFERENCES accounts (id),
  beoordeeld    timestamptz,
  toelichting   text CHECK (toelichting IS NULL OR length(toelichting) BETWEEN 5 AND 2000),
  dagster_run   text,
  afgerond      timestamptz,
  bewijs        jsonb,
  CHECK (beoordelaar IS NULL OR beoordelaar <> aanvrager),
  CHECK ((status = 'aangevraagd') = (beoordeeld IS NULL))
);
CREATE INDEX verwijderverzoeken_lopend ON verwijderverzoeken (aangemaakt) WHERE status IN ('aangevraagd', 'in-uitvoering');

-- Een beoordeelde aanvraag of een uitgevoerd verzoek gaat niet meer terug.
CREATE FUNCTION geen_terugweg() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('afgewezen', 'uitgevoerd', 'ingetrokken') THEN
    RAISE EXCEPTION 'afgerond: % kan niet meer wijzigen', OLD.status;
  END IF;
  IF OLD.beoordelaar IS NOT NULL AND NEW.beoordelaar IS DISTINCT FROM OLD.beoordelaar THEN
    RAISE EXCEPTION 'de beoordelaar ligt vast';
  END IF;
  IF NEW.aanvrager <> OLD.aanvrager OR NEW.aangemaakt <> OLD.aangemaakt THEN
    RAISE EXCEPTION 'aanvrager en tijdstip liggen vast';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER toegangsaanvragen_vast BEFORE UPDATE ON toegangsaanvragen FOR EACH ROW EXECUTE FUNCTION geen_terugweg();
CREATE TRIGGER verwijderverzoeken_vast BEFORE UPDATE ON verwijderverzoeken FOR EACH ROW EXECUTE FUNCTION geen_terugweg();

CREATE FUNCTION geen_verwijdering() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'aanvragen en verzoeken worden nooit verwijderd';
END $$;
CREATE TRIGGER toegangsaanvragen_blijven BEFORE DELETE OR TRUNCATE ON toegangsaanvragen FOR EACH STATEMENT EXECUTE FUNCTION geen_verwijdering();
CREATE TRIGGER verwijderverzoeken_blijven BEFORE DELETE OR TRUNCATE ON verwijderverzoeken FOR EACH STATEMENT EXECUTE FUNCTION geen_verwijdering();

GRANT SELECT, INSERT ON toegangsaanvragen, verwijderverzoeken TO df_portaal_app;
GRANT UPDATE (status, beoordelaar, beoordeeld, toelichting) ON toegangsaanvragen TO df_portaal_app;
GRANT UPDATE (status, beoordelaar, beoordeeld, toelichting, dagster_run, afgerond, bewijs) ON verwijderverzoeken TO df_portaal_app;
