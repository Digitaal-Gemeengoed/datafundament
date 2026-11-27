-- df-portaal, migratie 007: toegang voor een groep, en rechten in Lakekeeper (DF-ADR-020).
--
-- Een toegangsaanvraag kan voor een groep zijn. Dan geldt de toekenning voor
-- iedereen die lid is, ook wie er later bij komt; wie de groep verlaat, verliest
-- haar. De aanvrager moet lid zijn. De beoordelaar mag geen lid zijn: anders kent
-- hij zichzelf toegang toe (vier ogen). De naam van de groep wordt bewaard;
-- verdwijnt de groep, dan geldt de toekenning voor niemand meer. Daarom geen
-- verwijzende sleutel: aanvragen worden nooit gewijzigd of verwijderd.
SET search_path = beheer, public;

ALTER TABLE toegangsaanvragen
  ADD COLUMN groep uuid,
  ADD COLUMN groep_naam text CHECK (groep_naam IS NULL OR length(groep_naam) BETWEEN 1 AND 100),
  ADD CONSTRAINT toegangsaanvragen_groep CHECK ((groep IS NULL) = (groep_naam IS NULL));
CREATE INDEX toegangsaanvragen_groep_idx ON toegangsaanvragen (groep) WHERE groep IS NOT NULL;

CREATE FUNCTION groep_vier_ogen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.groep IS NULL THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'INSERT' AND NOT EXISTS (SELECT 1 FROM lidmaatschappen WHERE account = NEW.aanvrager AND groep = NEW.groep) THEN
    RAISE EXCEPTION 'de aanvrager is geen lid van de groep';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    IF NEW.groep IS DISTINCT FROM OLD.groep OR NEW.groep_naam IS DISTINCT FROM OLD.groep_naam THEN
      RAISE EXCEPTION 'de groep ligt vast';
    END IF;
    IF OLD.status = 'aangevraagd' AND NEW.status IN ('toegekend', 'afgewezen')
       AND EXISTS (SELECT 1 FROM lidmaatschappen WHERE account = NEW.beoordelaar AND groep = NEW.groep) THEN
      RAISE EXCEPTION 'een lid van de groep beoordeelt de aanvraag niet';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER toegangsaanvragen_groep BEFORE INSERT OR UPDATE ON toegangsaanvragen
  FOR EACH ROW EXECUTE FUNCTION groep_vier_ogen();

-- Wat het portaal in Lakekeeper heeft toegekend, zodat het dat ook weer kan
-- intrekken zonder aan rechten te komen die het installatiescript zette.
CREATE TABLE lakekeeper_toewijzingen (
  gebruiker  text NOT NULL CHECK (gebruiker ~ '^oidc~[A-Za-z0-9-]+$'),
  recht      text NOT NULL CHECK (recht IN ('describe', 'project_admin')),
  sinds      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (gebruiker, recht)
);
GRANT SELECT, INSERT, DELETE ON lakekeeper_toewijzingen TO df_portaal_app;
