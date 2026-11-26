-- Schema van de bron: een BRP-database met testpersonen (DF-ADR-010).
-- Gemaakt met: python brp.py schema  (niet met de hand wijzigen)
-- Testdata: vrijBRP-Balie fb9f41b, gba-test-people.zip (EUPL-1.2)

CREATE SCHEMA brp;

-- Eén rij per persoon. testsets: in welke testset(s) van vrijBRP de persoon voorkomt.
CREATE TABLE brp.persoonslijst (
  id bigserial PRIMARY KEY,
  a_nummer text NOT NULL UNIQUE,
  burgerservicenummer text,
  testsets text[] NOT NULL,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

-- Codes met hun omschrijving, zoals de testdata ze levert (vergelijkbaar met de
-- landelijke tabellen). element: groep en element van het LO BRP, bijvoorbeeld 09.10.
CREATE TABLE brp.codetabel (
  element text NOT NULL,
  code text NOT NULL,
  omschrijving text NOT NULL,
  PRIMARY KEY (element, code)
);

-- Categorie 01: persoon. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.persoon (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  a_nummer text,
  burgerservicenummer text,
  voornamen text,
  adellijke_titel_predikaat text,
  voorvoegsel_geslachtsnaam text,
  geslachtsnaam text,
  geboortedatum text,
  geboorteplaats text,
  geboorteland text,
  geslachtsaanduiding text,
  vorig_a_nummer text,
  volgend_a_nummer text,
  naamgebruik text,
  registergemeente_akte text,
  aktenummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  rni_deelnemer text,
  omschrijving_verdrag text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.persoon (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.persoon.a_nummer IS '01.01.10 a-nummer';
COMMENT ON COLUMN brp.persoon.burgerservicenummer IS '01.01.20 burgerservicenummer';
COMMENT ON COLUMN brp.persoon.voornamen IS '01.02.10 voornamen';
COMMENT ON COLUMN brp.persoon.adellijke_titel_predikaat IS '01.02.20 adellijke titel/predikaat';
COMMENT ON COLUMN brp.persoon.voorvoegsel_geslachtsnaam IS '01.02.30 voorvoegsel geslachtsnaam';
COMMENT ON COLUMN brp.persoon.geslachtsnaam IS '01.02.40 geslachtsnaam';
COMMENT ON COLUMN brp.persoon.geboortedatum IS '01.03.10 geboortedatum';
COMMENT ON COLUMN brp.persoon.geboorteplaats IS '01.03.20 geboorteplaats';
COMMENT ON COLUMN brp.persoon.geboorteland IS '01.03.30 geboorteland';
COMMENT ON COLUMN brp.persoon.geslachtsaanduiding IS '01.04.10 geslachtsaanduiding';
COMMENT ON COLUMN brp.persoon.vorig_a_nummer IS '01.20.10 vorig a-nummer';
COMMENT ON COLUMN brp.persoon.volgend_a_nummer IS '01.20.20 volgend a-nummer';
COMMENT ON COLUMN brp.persoon.naamgebruik IS '01.61.10 naamgebruik';
COMMENT ON COLUMN brp.persoon.registergemeente_akte IS '01.81.10 registergemeente akte';
COMMENT ON COLUMN brp.persoon.aktenummer IS '01.81.20 aktenummer';
COMMENT ON COLUMN brp.persoon.gemeente_document IS '01.82.10 gemeente document';
COMMENT ON COLUMN brp.persoon.datum_document IS '01.82.20 datum document';
COMMENT ON COLUMN brp.persoon.beschrijving_document IS '01.82.30 beschrijving document';
COMMENT ON COLUMN brp.persoon.aanduiding_gegevens_in_onderzoek IS '01.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.persoon.datum_ingang_onderzoek IS '01.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.persoon.datum_einde_onderzoek IS '01.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.persoon.indicatie_onjuist IS '01.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.persoon.ingangsdatum_geldigheid IS '01.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.persoon.volgcode_geldigheid IS '01.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.persoon.datum_van_opneming IS '01.86.10 datum van opneming';
COMMENT ON COLUMN brp.persoon.rni_deelnemer IS '01.88.10 RNI deelnemer';
COMMENT ON COLUMN brp.persoon.omschrijving_verdrag IS '01.88.20 omschrijving verdrag';

-- Categorie 02: ouder_1. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.ouder_1 (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  a_nummer text,
  burgerservicenummer text,
  voornamen text,
  adellijke_titel_predikaat text,
  voorvoegsel_geslachtsnaam text,
  geslachtsnaam text,
  geboortedatum text,
  geboorteplaats text,
  geboorteland text,
  geslachtsaanduiding text,
  datum_ingang_familierechtelijke_betrekking text,
  registergemeente_akte text,
  aktenummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.ouder_1 (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.ouder_1.a_nummer IS '02.01.10 a-nummer';
COMMENT ON COLUMN brp.ouder_1.burgerservicenummer IS '02.01.20 burgerservicenummer';
COMMENT ON COLUMN brp.ouder_1.voornamen IS '02.02.10 voornamen';
COMMENT ON COLUMN brp.ouder_1.adellijke_titel_predikaat IS '02.02.20 adellijke titel/predikaat';
COMMENT ON COLUMN brp.ouder_1.voorvoegsel_geslachtsnaam IS '02.02.30 voorvoegsel geslachtsnaam';
COMMENT ON COLUMN brp.ouder_1.geslachtsnaam IS '02.02.40 geslachtsnaam';
COMMENT ON COLUMN brp.ouder_1.geboortedatum IS '02.03.10 geboortedatum';
COMMENT ON COLUMN brp.ouder_1.geboorteplaats IS '02.03.20 geboorteplaats';
COMMENT ON COLUMN brp.ouder_1.geboorteland IS '02.03.30 geboorteland';
COMMENT ON COLUMN brp.ouder_1.geslachtsaanduiding IS '02.04.10 geslachtsaanduiding';
COMMENT ON COLUMN brp.ouder_1.datum_ingang_familierechtelijke_betrekking IS '02.62.10 datum ingang familierechtelijke betrekking';
COMMENT ON COLUMN brp.ouder_1.registergemeente_akte IS '02.81.10 registergemeente akte';
COMMENT ON COLUMN brp.ouder_1.aktenummer IS '02.81.20 aktenummer';
COMMENT ON COLUMN brp.ouder_1.gemeente_document IS '02.82.10 gemeente document';
COMMENT ON COLUMN brp.ouder_1.datum_document IS '02.82.20 datum document';
COMMENT ON COLUMN brp.ouder_1.beschrijving_document IS '02.82.30 beschrijving document';
COMMENT ON COLUMN brp.ouder_1.aanduiding_gegevens_in_onderzoek IS '02.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.ouder_1.datum_ingang_onderzoek IS '02.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.ouder_1.datum_einde_onderzoek IS '02.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.ouder_1.indicatie_onjuist IS '02.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.ouder_1.ingangsdatum_geldigheid IS '02.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.ouder_1.volgcode_geldigheid IS '02.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.ouder_1.datum_van_opneming IS '02.86.10 datum van opneming';

-- Categorie 03: ouder_2. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.ouder_2 (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  a_nummer text,
  burgerservicenummer text,
  voornamen text,
  adellijke_titel_predikaat text,
  voorvoegsel_geslachtsnaam text,
  geslachtsnaam text,
  geboortedatum text,
  geboorteplaats text,
  geboorteland text,
  geslachtsaanduiding text,
  datum_ingang_familierechtelijke_betrekking text,
  registergemeente_akte text,
  aktenummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.ouder_2 (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.ouder_2.a_nummer IS '03.01.10 a-nummer';
COMMENT ON COLUMN brp.ouder_2.burgerservicenummer IS '03.01.20 burgerservicenummer';
COMMENT ON COLUMN brp.ouder_2.voornamen IS '03.02.10 voornamen';
COMMENT ON COLUMN brp.ouder_2.adellijke_titel_predikaat IS '03.02.20 adellijke titel/predikaat';
COMMENT ON COLUMN brp.ouder_2.voorvoegsel_geslachtsnaam IS '03.02.30 voorvoegsel geslachtsnaam';
COMMENT ON COLUMN brp.ouder_2.geslachtsnaam IS '03.02.40 geslachtsnaam';
COMMENT ON COLUMN brp.ouder_2.geboortedatum IS '03.03.10 geboortedatum';
COMMENT ON COLUMN brp.ouder_2.geboorteplaats IS '03.03.20 geboorteplaats';
COMMENT ON COLUMN brp.ouder_2.geboorteland IS '03.03.30 geboorteland';
COMMENT ON COLUMN brp.ouder_2.geslachtsaanduiding IS '03.04.10 geslachtsaanduiding';
COMMENT ON COLUMN brp.ouder_2.datum_ingang_familierechtelijke_betrekking IS '03.62.10 datum ingang familierechtelijke betrekking';
COMMENT ON COLUMN brp.ouder_2.registergemeente_akte IS '03.81.10 registergemeente akte';
COMMENT ON COLUMN brp.ouder_2.aktenummer IS '03.81.20 aktenummer';
COMMENT ON COLUMN brp.ouder_2.gemeente_document IS '03.82.10 gemeente document';
COMMENT ON COLUMN brp.ouder_2.datum_document IS '03.82.20 datum document';
COMMENT ON COLUMN brp.ouder_2.beschrijving_document IS '03.82.30 beschrijving document';
COMMENT ON COLUMN brp.ouder_2.aanduiding_gegevens_in_onderzoek IS '03.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.ouder_2.datum_ingang_onderzoek IS '03.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.ouder_2.datum_einde_onderzoek IS '03.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.ouder_2.indicatie_onjuist IS '03.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.ouder_2.ingangsdatum_geldigheid IS '03.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.ouder_2.volgcode_geldigheid IS '03.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.ouder_2.datum_van_opneming IS '03.86.10 datum van opneming';

-- Categorie 04: nationaliteit. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.nationaliteit (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  nationaliteit text,
  reden_opname_nationaliteit text,
  reden_beeindigen_nationaliteit text,
  aanduiding_bijzonder_nederlanderschap text,
  eu_persoonsnummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  rni_deelnemer text,
  omschrijving_verdrag text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.nationaliteit (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.nationaliteit.nationaliteit IS '04.05.10 nationaliteit';
COMMENT ON COLUMN brp.nationaliteit.reden_opname_nationaliteit IS '04.63.10 reden opname nationaliteit';
COMMENT ON COLUMN brp.nationaliteit.reden_beeindigen_nationaliteit IS '04.64.10 reden beëindigen nationaliteit';
COMMENT ON COLUMN brp.nationaliteit.aanduiding_bijzonder_nederlanderschap IS '04.65.10 aanduiding bijzonder Nederlanderschap';
COMMENT ON COLUMN brp.nationaliteit.eu_persoonsnummer IS '04.73.10 EU-persoonsnummer';
COMMENT ON COLUMN brp.nationaliteit.gemeente_document IS '04.82.10 gemeente document';
COMMENT ON COLUMN brp.nationaliteit.datum_document IS '04.82.20 datum document';
COMMENT ON COLUMN brp.nationaliteit.beschrijving_document IS '04.82.30 beschrijving document';
COMMENT ON COLUMN brp.nationaliteit.aanduiding_gegevens_in_onderzoek IS '04.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.nationaliteit.datum_ingang_onderzoek IS '04.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.nationaliteit.datum_einde_onderzoek IS '04.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.nationaliteit.indicatie_onjuist IS '04.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.nationaliteit.ingangsdatum_geldigheid IS '04.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.nationaliteit.volgcode_geldigheid IS '04.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.nationaliteit.datum_van_opneming IS '04.86.10 datum van opneming';
COMMENT ON COLUMN brp.nationaliteit.rni_deelnemer IS '04.88.10 RNI deelnemer';
COMMENT ON COLUMN brp.nationaliteit.omschrijving_verdrag IS '04.88.20 omschrijving verdrag';

-- Categorie 05: huwelijk. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.huwelijk (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  a_nummer text,
  burgerservicenummer text,
  voornamen text,
  adellijke_titel_predikaat text,
  voorvoegsel_geslachtsnaam text,
  geslachtsnaam text,
  geboortedatum text,
  geboorteplaats text,
  geboorteland text,
  geslachtsaanduiding text,
  datum_huwelijkssluiting_aangaan_gps text,
  plaats_huwelijkssluiting_aangaan_gps text,
  land_huwelijkssluiting_aangaan_gps text,
  datum_ontbinding_huwelijk_gps text,
  plaats_ontbinding_huwelijk_gps text,
  land_ontbinding_huwelijk_gps text,
  reden_ontbinding_huwelijk_gps text,
  soort_verbintenis text,
  registergemeente_akte text,
  aktenummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.huwelijk (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.huwelijk.a_nummer IS '05.01.10 a-nummer';
COMMENT ON COLUMN brp.huwelijk.burgerservicenummer IS '05.01.20 burgerservicenummer';
COMMENT ON COLUMN brp.huwelijk.voornamen IS '05.02.10 voornamen';
COMMENT ON COLUMN brp.huwelijk.adellijke_titel_predikaat IS '05.02.20 adellijke titel/predikaat';
COMMENT ON COLUMN brp.huwelijk.voorvoegsel_geslachtsnaam IS '05.02.30 voorvoegsel geslachtsnaam';
COMMENT ON COLUMN brp.huwelijk.geslachtsnaam IS '05.02.40 geslachtsnaam';
COMMENT ON COLUMN brp.huwelijk.geboortedatum IS '05.03.10 geboortedatum';
COMMENT ON COLUMN brp.huwelijk.geboorteplaats IS '05.03.20 geboorteplaats';
COMMENT ON COLUMN brp.huwelijk.geboorteland IS '05.03.30 geboorteland';
COMMENT ON COLUMN brp.huwelijk.geslachtsaanduiding IS '05.04.10 geslachtsaanduiding';
COMMENT ON COLUMN brp.huwelijk.datum_huwelijkssluiting_aangaan_gps IS '05.06.10 datum huwelijkssluiting/aangaan GPS';
COMMENT ON COLUMN brp.huwelijk.plaats_huwelijkssluiting_aangaan_gps IS '05.06.20 plaats huwelijkssluiting/aangaan GPS';
COMMENT ON COLUMN brp.huwelijk.land_huwelijkssluiting_aangaan_gps IS '05.06.30 land huwelijkssluiting/aangaan GPS';
COMMENT ON COLUMN brp.huwelijk.datum_ontbinding_huwelijk_gps IS '05.07.10 datum ontbinding huwelijk/GPS';
COMMENT ON COLUMN brp.huwelijk.plaats_ontbinding_huwelijk_gps IS '05.07.20 plaats ontbinding huwelijk/GPS';
COMMENT ON COLUMN brp.huwelijk.land_ontbinding_huwelijk_gps IS '05.07.30 land ontbinding huwelijk/GPS';
COMMENT ON COLUMN brp.huwelijk.reden_ontbinding_huwelijk_gps IS '05.07.40 reden ontbinding huwelijk/GPS';
COMMENT ON COLUMN brp.huwelijk.soort_verbintenis IS '05.15.10 soort verbintenis';
COMMENT ON COLUMN brp.huwelijk.registergemeente_akte IS '05.81.10 registergemeente akte';
COMMENT ON COLUMN brp.huwelijk.aktenummer IS '05.81.20 aktenummer';
COMMENT ON COLUMN brp.huwelijk.gemeente_document IS '05.82.10 gemeente document';
COMMENT ON COLUMN brp.huwelijk.datum_document IS '05.82.20 datum document';
COMMENT ON COLUMN brp.huwelijk.beschrijving_document IS '05.82.30 beschrijving document';
COMMENT ON COLUMN brp.huwelijk.aanduiding_gegevens_in_onderzoek IS '05.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.huwelijk.datum_ingang_onderzoek IS '05.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.huwelijk.datum_einde_onderzoek IS '05.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.huwelijk.indicatie_onjuist IS '05.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.huwelijk.ingangsdatum_geldigheid IS '05.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.huwelijk.volgcode_geldigheid IS '05.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.huwelijk.datum_van_opneming IS '05.86.10 datum van opneming';

-- Categorie 06: overlijden. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.overlijden (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  datum_overlijden text,
  plaats_overlijden text,
  land_overlijden text,
  registergemeente_akte text,
  aktenummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  rni_deelnemer text,
  omschrijving_verdrag text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.overlijden (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.overlijden.datum_overlijden IS '06.08.10 datum overlijden';
COMMENT ON COLUMN brp.overlijden.plaats_overlijden IS '06.08.20 plaats overlijden';
COMMENT ON COLUMN brp.overlijden.land_overlijden IS '06.08.30 land overlijden';
COMMENT ON COLUMN brp.overlijden.registergemeente_akte IS '06.81.10 registergemeente akte';
COMMENT ON COLUMN brp.overlijden.aktenummer IS '06.81.20 aktenummer';
COMMENT ON COLUMN brp.overlijden.gemeente_document IS '06.82.10 gemeente document';
COMMENT ON COLUMN brp.overlijden.datum_document IS '06.82.20 datum document';
COMMENT ON COLUMN brp.overlijden.beschrijving_document IS '06.82.30 beschrijving document';
COMMENT ON COLUMN brp.overlijden.aanduiding_gegevens_in_onderzoek IS '06.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.overlijden.datum_ingang_onderzoek IS '06.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.overlijden.datum_einde_onderzoek IS '06.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.overlijden.indicatie_onjuist IS '06.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.overlijden.ingangsdatum_geldigheid IS '06.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.overlijden.volgcode_geldigheid IS '06.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.overlijden.datum_van_opneming IS '06.86.10 datum van opneming';
COMMENT ON COLUMN brp.overlijden.rni_deelnemer IS '06.88.10 RNI deelnemer';
COMMENT ON COLUMN brp.overlijden.omschrijving_verdrag IS '06.88.20 omschrijving verdrag';

-- Categorie 07: inschrijving. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.inschrijving (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  gemeente_blokkering_pl text,
  datum_ingang_blokkering_pl text,
  datum_opschorting_bijhouding text,
  omschrijving_reden_opschorting_bijhouding text,
  datum_eerste_inschrijving_gba text,
  gemeente_waar_de_pk_zich_bevindt text,
  indicatie_geheim text,
  datum_verificatie text,
  omschrijving_verificatie text,
  versienummer text,
  datumtijdstempel text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  pk_gegevens_volledig_meegeconverteerd text,
  rni_deelnemer text,
  omschrijving_verdrag text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.inschrijving (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.inschrijving.gemeente_blokkering_pl IS '07.66.10 gemeente blokkering PL';
COMMENT ON COLUMN brp.inschrijving.datum_ingang_blokkering_pl IS '07.66.20 datum ingang blokkering PL';
COMMENT ON COLUMN brp.inschrijving.datum_opschorting_bijhouding IS '07.67.10 datum opschorting bijhouding';
COMMENT ON COLUMN brp.inschrijving.omschrijving_reden_opschorting_bijhouding IS '07.67.20 omschrijving reden opschorting bijhouding';
COMMENT ON COLUMN brp.inschrijving.datum_eerste_inschrijving_gba IS '07.68.10 datum eerste inschrijving GBA';
COMMENT ON COLUMN brp.inschrijving.gemeente_waar_de_pk_zich_bevindt IS '07.69.10 gemeente waar de PK zich bevindt';
COMMENT ON COLUMN brp.inschrijving.indicatie_geheim IS '07.70.10 indicatie geheim';
COMMENT ON COLUMN brp.inschrijving.datum_verificatie IS '07.71.10 Datum verificatie';
COMMENT ON COLUMN brp.inschrijving.omschrijving_verificatie IS '07.71.20 Omschrijving verificatie';
COMMENT ON COLUMN brp.inschrijving.versienummer IS '07.80.10 versienummer';
COMMENT ON COLUMN brp.inschrijving.datumtijdstempel IS '07.80.20 datumtijdstempel';
COMMENT ON COLUMN brp.inschrijving.ingangsdatum_geldigheid IS '07.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.inschrijving.volgcode_geldigheid IS '07.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.inschrijving.datum_van_opneming IS '07.86.10 datum van opneming';
COMMENT ON COLUMN brp.inschrijving.pk_gegevens_volledig_meegeconverteerd IS '07.87.10 PK-gegevens volledig meegeconverteerd';
COMMENT ON COLUMN brp.inschrijving.rni_deelnemer IS '07.88.10 RNI deelnemer';
COMMENT ON COLUMN brp.inschrijving.omschrijving_verdrag IS '07.88.20 omschrijving verdrag';

-- Categorie 08: verblijfplaats. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.verblijfplaats (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  gemeente_van_inschrijving text,
  code_gemeente_van_inschrijving text,
  datum_inschrijving text,
  functie_adres text,
  gemeentedeel text,
  datum_aanvang_adreshouding text,
  straatnaam text,
  straatnaam_officieel text,
  straatnaam_nen text,
  openbare_ruimte text,
  huisnummer text,
  huisletter text,
  huisnummertoevoeging text,
  aanduiding_bij_huisnummer text,
  postcode text,
  woonplaatsnaam text,
  identificatie_verblijfplaats text,
  identificatiecode_nummeraanduiding text,
  locatiebeschrijving text,
  land_waarnaar_vertrokken text,
  datum_vertrek_uit_nederland text,
  adres_buitenland_waarnaar_vertrokken_1 text,
  adres_buitenland_waarnaar_vertrokken_2 text,
  adres_buitenland_waarnaar_vertrokken_3 text,
  land_vanwaar_ingeschreven text,
  datum_vestiging_in_nederland text,
  omschrijving_van_de_aangifte_adreshouding text,
  indicatie_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  rni_deelnemer text,
  omschrijving_verdrag text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.verblijfplaats (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.verblijfplaats.gemeente_van_inschrijving IS '08.09.10 gemeente van inschrijving';
COMMENT ON COLUMN brp.verblijfplaats.code_gemeente_van_inschrijving IS '08.09.11 code gemeente van inschrijving';
COMMENT ON COLUMN brp.verblijfplaats.datum_inschrijving IS '08.09.20 datum inschrijving';
COMMENT ON COLUMN brp.verblijfplaats.functie_adres IS '08.10.10 functie adres';
COMMENT ON COLUMN brp.verblijfplaats.gemeentedeel IS '08.10.20 gemeentedeel';
COMMENT ON COLUMN brp.verblijfplaats.datum_aanvang_adreshouding IS '08.10.30 datum aanvang adreshouding';
COMMENT ON COLUMN brp.verblijfplaats.straatnaam IS '08.11.10 straatnaam';
COMMENT ON COLUMN brp.verblijfplaats.straatnaam_officieel IS '08.11.11 straatnaam (officieel)';
COMMENT ON COLUMN brp.verblijfplaats.straatnaam_nen IS '08.11.12 straatnaam (NEN)';
COMMENT ON COLUMN brp.verblijfplaats.openbare_ruimte IS '08.11.15 openbare ruimte';
COMMENT ON COLUMN brp.verblijfplaats.huisnummer IS '08.11.20 huisnummer';
COMMENT ON COLUMN brp.verblijfplaats.huisletter IS '08.11.30 huisletter';
COMMENT ON COLUMN brp.verblijfplaats.huisnummertoevoeging IS '08.11.40 huisnummertoevoeging';
COMMENT ON COLUMN brp.verblijfplaats.aanduiding_bij_huisnummer IS '08.11.50 aanduiding bij huisnummer';
COMMENT ON COLUMN brp.verblijfplaats.postcode IS '08.11.60 postcode';
COMMENT ON COLUMN brp.verblijfplaats.woonplaatsnaam IS '08.11.70 woonplaatsnaam';
COMMENT ON COLUMN brp.verblijfplaats.identificatie_verblijfplaats IS '08.11.80 identificatie verblijfplaats';
COMMENT ON COLUMN brp.verblijfplaats.identificatiecode_nummeraanduiding IS '08.11.90 identificatiecode nummeraanduiding';
COMMENT ON COLUMN brp.verblijfplaats.locatiebeschrijving IS '08.12.10 locatiebeschrijving';
COMMENT ON COLUMN brp.verblijfplaats.land_waarnaar_vertrokken IS '08.13.10 land waarnaar vertrokken';
COMMENT ON COLUMN brp.verblijfplaats.datum_vertrek_uit_nederland IS '08.13.20 datum vertrek uit Nederland';
COMMENT ON COLUMN brp.verblijfplaats.adres_buitenland_waarnaar_vertrokken_1 IS '08.13.30 adres buitenland waarnaar vertrokken 1';
COMMENT ON COLUMN brp.verblijfplaats.adres_buitenland_waarnaar_vertrokken_2 IS '08.13.40 adres buitenland waarnaar vertrokken 2';
COMMENT ON COLUMN brp.verblijfplaats.adres_buitenland_waarnaar_vertrokken_3 IS '08.13.50 adres buitenland waarnaar vertrokken 3';
COMMENT ON COLUMN brp.verblijfplaats.land_vanwaar_ingeschreven IS '08.14.10 land vanwaar ingeschreven';
COMMENT ON COLUMN brp.verblijfplaats.datum_vestiging_in_nederland IS '08.14.20 datum vestiging in Nederland';
COMMENT ON COLUMN brp.verblijfplaats.omschrijving_van_de_aangifte_adreshouding IS '08.72.10 omschrijving van de aangifte adreshouding';
COMMENT ON COLUMN brp.verblijfplaats.indicatie_document IS '08.75.10 indicatie document';
COMMENT ON COLUMN brp.verblijfplaats.aanduiding_gegevens_in_onderzoek IS '08.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.verblijfplaats.datum_ingang_onderzoek IS '08.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.verblijfplaats.datum_einde_onderzoek IS '08.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.verblijfplaats.indicatie_onjuist IS '08.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.verblijfplaats.ingangsdatum_geldigheid IS '08.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.verblijfplaats.volgcode_geldigheid IS '08.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.verblijfplaats.datum_van_opneming IS '08.86.10 datum van opneming';
COMMENT ON COLUMN brp.verblijfplaats.rni_deelnemer IS '08.88.10 RNI deelnemer';
COMMENT ON COLUMN brp.verblijfplaats.omschrijving_verdrag IS '08.88.20 omschrijving verdrag';

-- Categorie 09: kind. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.kind (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  a_nummer text,
  burgerservicenummer text,
  voornamen text,
  adellijke_titel_predikaat text,
  voorvoegsel_geslachtsnaam text,
  geslachtsnaam text,
  geboortedatum text,
  geboorteplaats text,
  geboorteland text,
  registergemeente_akte text,
  aktenummer text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  registratie_betrekking text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.kind (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.kind.a_nummer IS '09.01.10 a-nummer';
COMMENT ON COLUMN brp.kind.burgerservicenummer IS '09.01.20 burgerservicenummer';
COMMENT ON COLUMN brp.kind.voornamen IS '09.02.10 voornamen';
COMMENT ON COLUMN brp.kind.adellijke_titel_predikaat IS '09.02.20 adellijke titel/predikaat';
COMMENT ON COLUMN brp.kind.voorvoegsel_geslachtsnaam IS '09.02.30 voorvoegsel geslachtsnaam';
COMMENT ON COLUMN brp.kind.geslachtsnaam IS '09.02.40 geslachtsnaam';
COMMENT ON COLUMN brp.kind.geboortedatum IS '09.03.10 geboortedatum';
COMMENT ON COLUMN brp.kind.geboorteplaats IS '09.03.20 geboorteplaats';
COMMENT ON COLUMN brp.kind.geboorteland IS '09.03.30 geboorteland';
COMMENT ON COLUMN brp.kind.registergemeente_akte IS '09.81.10 registergemeente akte';
COMMENT ON COLUMN brp.kind.aktenummer IS '09.81.20 aktenummer';
COMMENT ON COLUMN brp.kind.gemeente_document IS '09.82.10 gemeente document';
COMMENT ON COLUMN brp.kind.datum_document IS '09.82.20 datum document';
COMMENT ON COLUMN brp.kind.beschrijving_document IS '09.82.30 beschrijving document';
COMMENT ON COLUMN brp.kind.aanduiding_gegevens_in_onderzoek IS '09.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.kind.datum_ingang_onderzoek IS '09.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.kind.datum_einde_onderzoek IS '09.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.kind.indicatie_onjuist IS '09.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.kind.ingangsdatum_geldigheid IS '09.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.kind.volgcode_geldigheid IS '09.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.kind.datum_van_opneming IS '09.86.10 datum van opneming';
COMMENT ON COLUMN brp.kind.registratie_betrekking IS '09.89.10 registratie betrekking';

-- Categorie 10: verblijfstitel. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.verblijfstitel (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  aanduiding_verblijfstitel text,
  aanduiding_verblijfstitel_3911 text,
  datum_einde_verblijfstitel text,
  ingangsdatum_verblijfstitel text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.verblijfstitel (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.verblijfstitel.aanduiding_verblijfstitel IS '10.39.10 aanduiding verblijfstitel';
COMMENT ON COLUMN brp.verblijfstitel.aanduiding_verblijfstitel_3911 IS '10.39.11 aanduiding verblijfstitel';
COMMENT ON COLUMN brp.verblijfstitel.datum_einde_verblijfstitel IS '10.39.20 datum einde verblijfstitel';
COMMENT ON COLUMN brp.verblijfstitel.ingangsdatum_verblijfstitel IS '10.39.30 ingangsdatum verblijfstitel';
COMMENT ON COLUMN brp.verblijfstitel.aanduiding_gegevens_in_onderzoek IS '10.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.verblijfstitel.datum_ingang_onderzoek IS '10.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.verblijfstitel.datum_einde_onderzoek IS '10.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.verblijfstitel.indicatie_onjuist IS '10.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.verblijfstitel.ingangsdatum_geldigheid IS '10.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.verblijfstitel.volgcode_geldigheid IS '10.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.verblijfstitel.datum_van_opneming IS '10.86.10 datum van opneming';

-- Categorie 11: gezag. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.gezag (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  gezag_minderjarige text,
  curatele text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.gezag (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.gezag.gezag_minderjarige IS '11.32.10 gezag minderjarige';
COMMENT ON COLUMN brp.gezag.curatele IS '11.33.10 curatele';
COMMENT ON COLUMN brp.gezag.gemeente_document IS '11.82.10 gemeente document';
COMMENT ON COLUMN brp.gezag.datum_document IS '11.82.20 datum document';
COMMENT ON COLUMN brp.gezag.beschrijving_document IS '11.82.30 beschrijving document';
COMMENT ON COLUMN brp.gezag.aanduiding_gegevens_in_onderzoek IS '11.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.gezag.datum_ingang_onderzoek IS '11.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.gezag.datum_einde_onderzoek IS '11.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.gezag.indicatie_onjuist IS '11.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.gezag.ingangsdatum_geldigheid IS '11.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.gezag.volgcode_geldigheid IS '11.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.gezag.datum_van_opneming IS '11.86.10 datum van opneming';

-- Categorie 12: reisdocument. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.reisdocument (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  nederlands_reisdocument text,
  nummer_document text,
  datum_uitgifte text,
  autoriteit_van_afgifte text,
  datum_einde_geldigheid text,
  datum_inhouding_vermissing text,
  aanduiding_inhouding_vermissing text,
  lengte_houder text,
  signalering_met_betrekking_tot_verstrekken_nl_reisdocument text,
  buitenlands_reisdocument text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  aanduiding_gegevens_in_onderzoek text,
  datum_ingang_onderzoek text,
  datum_einde_onderzoek text,
  indicatie_onjuist text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.reisdocument (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.reisdocument.nederlands_reisdocument IS '12.35.10 Nederlands reisdocument';
COMMENT ON COLUMN brp.reisdocument.nummer_document IS '12.35.20 nummer document';
COMMENT ON COLUMN brp.reisdocument.datum_uitgifte IS '12.35.30 datum uitgifte';
COMMENT ON COLUMN brp.reisdocument.autoriteit_van_afgifte IS '12.35.40 autoriteit van afgifte';
COMMENT ON COLUMN brp.reisdocument.datum_einde_geldigheid IS '12.35.50 datum einde geldigheid';
COMMENT ON COLUMN brp.reisdocument.datum_inhouding_vermissing IS '12.35.60 datum inhouding/vermissing';
COMMENT ON COLUMN brp.reisdocument.aanduiding_inhouding_vermissing IS '12.35.70 aanduiding inhouding/vermissing';
COMMENT ON COLUMN brp.reisdocument.lengte_houder IS '12.35.80 lengte houder';
COMMENT ON COLUMN brp.reisdocument.signalering_met_betrekking_tot_verstrekken_nl_reisdocument IS '12.36.10 signalering met betrekking tot verstrekken NL reisdocument';
COMMENT ON COLUMN brp.reisdocument.buitenlands_reisdocument IS '12.37.10 buitenlands reisdocument';
COMMENT ON COLUMN brp.reisdocument.gemeente_document IS '12.82.10 gemeente document';
COMMENT ON COLUMN brp.reisdocument.datum_document IS '12.82.20 datum document';
COMMENT ON COLUMN brp.reisdocument.beschrijving_document IS '12.82.30 beschrijving document';
COMMENT ON COLUMN brp.reisdocument.aanduiding_gegevens_in_onderzoek IS '12.83.10 aanduiding gegevens in onderzoek';
COMMENT ON COLUMN brp.reisdocument.datum_ingang_onderzoek IS '12.83.20 datum ingang onderzoek';
COMMENT ON COLUMN brp.reisdocument.datum_einde_onderzoek IS '12.83.30 datum einde onderzoek';
COMMENT ON COLUMN brp.reisdocument.indicatie_onjuist IS '12.84.10 indicatie onjuist';
COMMENT ON COLUMN brp.reisdocument.ingangsdatum_geldigheid IS '12.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.reisdocument.volgcode_geldigheid IS '12.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.reisdocument.datum_van_opneming IS '12.86.10 datum van opneming';

-- Categorie 13: kiesrecht. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.kiesrecht (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  aanduiding_europees_kiesrecht text,
  datum_verzoek_of_mededeling_europees_kiesrecht text,
  einddatum_uitsluiting_europees_kiesrecht text,
  aanduiding_uitgesloten_kiesrecht text,
  einddatum_uitsluiting_kiesrecht text,
  gemeente_document text,
  datum_document text,
  beschrijving_document text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  datum_van_opneming text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.kiesrecht (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.kiesrecht.aanduiding_europees_kiesrecht IS '13.31.10 aanduiding europees kiesrecht';
COMMENT ON COLUMN brp.kiesrecht.datum_verzoek_of_mededeling_europees_kiesrecht IS '13.31.20 datum verzoek of mededeling europees kiesrecht';
COMMENT ON COLUMN brp.kiesrecht.einddatum_uitsluiting_europees_kiesrecht IS '13.31.30 einddatum uitsluiting europees kiesrecht';
COMMENT ON COLUMN brp.kiesrecht.aanduiding_uitgesloten_kiesrecht IS '13.38.10 aanduiding uitgesloten kiesrecht';
COMMENT ON COLUMN brp.kiesrecht.einddatum_uitsluiting_kiesrecht IS '13.38.20 einddatum uitsluiting kiesrecht';
COMMENT ON COLUMN brp.kiesrecht.gemeente_document IS '13.82.10 gemeente document';
COMMENT ON COLUMN brp.kiesrecht.datum_document IS '13.82.20 datum document';
COMMENT ON COLUMN brp.kiesrecht.beschrijving_document IS '13.82.30 beschrijving document';
COMMENT ON COLUMN brp.kiesrecht.ingangsdatum_geldigheid IS '13.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.kiesrecht.volgcode_geldigheid IS '13.85.11 volgcode geldigheid';
COMMENT ON COLUMN brp.kiesrecht.datum_van_opneming IS '13.86.10 datum van opneming';

-- Categorie 30: diversen. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.diversen (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  gezinsverhouding text,
  regel text,
  aantekening_opmerking text,
  kenmerk text,
  kenmerk_omschrijving text,
  datum_pl_verstrekt text,
  ots text,
  signaal text,
  correspondentie_adres_1 text,
  correspondentie_adres_2 text,
  a_nummer text,
  ingangsdatum_geldigheid text,
  volgcode_geldigheid text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.diversen (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.diversen.gezinsverhouding IS '30.00.05 gezinsverhouding';
COMMENT ON COLUMN brp.diversen.regel IS '30.00.06 regel';
COMMENT ON COLUMN brp.diversen.aantekening_opmerking IS '30.00.08 aantekening opmerking';
COMMENT ON COLUMN brp.diversen.kenmerk IS '30.00.20 kenmerk';
COMMENT ON COLUMN brp.diversen.kenmerk_omschrijving IS '30.00.21 kenmerk omschrijving';
COMMENT ON COLUMN brp.diversen.datum_pl_verstrekt IS '30.00.30 datum PL verstrekt';
COMMENT ON COLUMN brp.diversen.ots IS '30.00.40 OTS';
COMMENT ON COLUMN brp.diversen.signaal IS '30.00.50 signaal';
COMMENT ON COLUMN brp.diversen.correspondentie_adres_1 IS '30.00.60 correspondentie-adres (1)';
COMMENT ON COLUMN brp.diversen.correspondentie_adres_2 IS '30.00.61 correspondentie-adres (2)';
COMMENT ON COLUMN brp.diversen.a_nummer IS '30.01.10 a-nummer';
COMMENT ON COLUMN brp.diversen.ingangsdatum_geldigheid IS '30.85.10 ingangsdatum geldigheid';
COMMENT ON COLUMN brp.diversen.volgcode_geldigheid IS '30.85.11 volgcode geldigheid';

-- Categorie 32: woningkaart. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.woningkaart (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  gezinsverhouding text,
  regel text,
  aantekening_omschrijving text,
  aantekening_opmerking text,
  datum_einde_adreshouding text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.woningkaart (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.woningkaart.gezinsverhouding IS '32.00.05 gezinsverhouding';
COMMENT ON COLUMN brp.woningkaart.regel IS '32.00.06 regel';
COMMENT ON COLUMN brp.woningkaart.aantekening_omschrijving IS '32.00.07 aantekening omschrijving';
COMMENT ON COLUMN brp.woningkaart.aantekening_opmerking IS '32.00.08 aantekening opmerking';
COMMENT ON COLUMN brp.woningkaart.datum_einde_adreshouding IS '32.00.09 datum einde adreshouding';

-- Categorie 34: lokale_afnemersindicatie. Per stapel de records; actueel = de actuele stand,
-- de andere rijen zijn historie. volgnr: de volgorde in de bron.
CREATE TABLE brp.lokale_afnemersindicatie (
  id bigserial PRIMARY KEY,
  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),
  stapel integer NOT NULL,
  volgnr integer NOT NULL,
  actueel boolean NOT NULL,
  onjuist boolean NOT NULL DEFAULT false,
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  regel text,
  aantekening_omschrijving text,
  aantekening_opmerking text,
  UNIQUE (pl_id, stapel, volgnr)
);
CREATE INDEX ON brp.lokale_afnemersindicatie (pl_id) WHERE actueel;
COMMENT ON COLUMN brp.lokale_afnemersindicatie.regel IS '34.00.06 regel';
COMMENT ON COLUMN brp.lokale_afnemersindicatie.aantekening_omschrijving IS '34.00.07 aantekening omschrijving';
COMMENT ON COLUMN brp.lokale_afnemersindicatie.aantekening_opmerking IS '34.00.08 aantekening opmerking';
