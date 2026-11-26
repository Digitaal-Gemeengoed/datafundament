-- Synthetische bronnen naast de BRP (DF-ADR-010): elk schema is een
-- gemeentelijke applicatie. Gekoppeld aan de BRP via BSN, en aan elkaar via de
-- BAG (nummeraanduiding, verblijfsobject, pand). Alle data is verzonnen.
--
-- Elke tabel heeft id (technische sleutel) en gewijzigd_op, zodat de ingestie
-- (dlt, incrementeel) voor alle bronnen hetzelfde werkt. Idempotent.

-- === BAG: de gemeentelijke BAG-registratie =======================================
CREATE SCHEMA IF NOT EXISTS bag;

CREATE TABLE IF NOT EXISTS bag.woonplaats (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,          -- 4 posities
  naam text NOT NULL,
  gemeentecode text NOT NULL,
  status text NOT NULL,                        -- Woonplaats aangewezen
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bag.openbare_ruimte (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,          -- gemeentecode + 30 + volgnummer
  naam text NOT NULL,
  type text NOT NULL,                          -- Weg, Water, Terrein, ...
  woonplaats_identificatie text NOT NULL,
  status text NOT NULL,                        -- Naamgeving uitgegeven
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bag.nummeraanduiding (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,          -- gemeentecode + 20 + volgnummer
  huisnummer integer NOT NULL,
  huisletter text,
  huisnummertoevoeging text,
  postcode text,
  type_adresseerbaar_object text NOT NULL,     -- Verblijfsobject
  openbare_ruimte_identificatie text NOT NULL,
  status text NOT NULL,                        -- Naamgeving uitgegeven
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bag.pand (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,          -- gemeentecode + 10 + volgnummer
  oorspronkelijk_bouwjaar integer NOT NULL,
  status text NOT NULL,                        -- Pand in gebruik, ...
  geometrie_wkt text NOT NULL,                 -- RD (EPSG:28992), synthetisch
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bag.verblijfsobject (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,          -- gemeentecode + 01 + volgnummer
  hoofdadres_identificatie text NOT NULL,      -- nummeraanduiding
  pand_identificatie text NOT NULL,
  gebruiksdoel text NOT NULL,                  -- woonfunctie, winkelfunctie, ...
  oppervlakte integer NOT NULL,                -- m2
  status text NOT NULL,                        -- Verblijfsobject in gebruik, ...
  geometrie_wkt text NOT NULL,                 -- punt in RD, synthetisch
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

-- === WOZ: waardering onroerende zaken =============================================
CREATE SCHEMA IF NOT EXISTS woz;

CREATE TABLE IF NOT EXISTS woz.object (
  id bigserial PRIMARY KEY,
  wozobjectnummer text NOT NULL UNIQUE,        -- 12 posities
  verblijfsobject_identificatie text NOT NULL,
  soort_object text NOT NULL,                  -- woning, winkel, kantoor, ...
  gemeentecode text NOT NULL,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS woz.waarde (
  id bigserial PRIMARY KEY,
  wozobjectnummer text NOT NULL,
  waardepeildatum date NOT NULL,               -- 1 januari van het jaar voor het belastingjaar
  vastgestelde_waarde integer NOT NULL,        -- euro
  gewijzigd_op timestamptz NOT NULL DEFAULT now(),
  UNIQUE (wozobjectnummer, waardepeildatum)
);

CREATE TABLE IF NOT EXISTS woz.belanghebbende (
  id bigserial PRIMARY KEY,
  wozobjectnummer text NOT NULL,
  rol text NOT NULL,                           -- eigenaar, gebruiker
  bsn text,                                    -- natuurlijk persoon
  nnp_id text,                                 -- niet-natuurlijk persoon
  nnp_naam text,
  begindatum date NOT NULL,
  einddatum date,                              -- verkocht, verhuisd, overleden
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

-- Bijgekomen na de eerste versie (DF-ADR-014): ook in een bestaande database.
ALTER TABLE woz.belanghebbende ADD COLUMN IF NOT EXISTS begindatum date;
ALTER TABLE woz.belanghebbende ADD COLUMN IF NOT EXISTS einddatum date;

-- === Belastingen: aanslagen ========================================================
CREATE SCHEMA IF NOT EXISTS belastingen;

CREATE TABLE IF NOT EXISTS belastingen.aanslag (
  id bigserial PRIMARY KEY,
  aanslagnummer text NOT NULL UNIQUE,
  belastingjaar integer NOT NULL,
  soort text NOT NULL,                         -- OZB eigenaren, afvalstoffenheffing
  subject_bsn text,
  subject_nnp_id text,
  wozobjectnummer text,
  bedrag numeric(10, 2) NOT NULL,
  dagtekening date NOT NULL,
  status text NOT NULL,                        -- openstaand, betaald, aanmaning verstuurd, kwijtgescholden
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

-- === Meldingen openbare ruimte (zoals Signalen) ===================================
CREATE SCHEMA IF NOT EXISTS mor;

CREATE TABLE IF NOT EXISTS mor.melding (
  id bigserial PRIMARY KEY,
  signaalnummer text NOT NULL UNIQUE,
  hoofdcategorie text NOT NULL,
  subcategorie text NOT NULL,
  omschrijving text NOT NULL,
  nummeraanduiding_identificatie text,         -- dichtstbijzijnde adres
  locatie_wkt text NOT NULL,                   -- punt in RD
  melder_bsn text,                             -- leeg = anoniem
  aangemaakt_op timestamptz NOT NULL,
  status text NOT NULL,                        -- gemeld, in behandeling, afgehandeld
  afgehandeld_op timestamptz,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mor.status (
  id bigserial PRIMARY KEY,
  signaalnummer text NOT NULL,
  status text NOT NULL,
  tijdstip timestamptz NOT NULL,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

-- === Zaken (zoals de ZGW-API's) ===================================================
CREATE SCHEMA IF NOT EXISTS zaken;

CREATE TABLE IF NOT EXISTS zaken.zaaktype (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,
  omschrijving text NOT NULL,
  doorlooptijd_dagen integer NOT NULL,         -- wettelijke of afgesproken termijn
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS zaken.zaak (
  id bigserial PRIMARY KEY,
  identificatie text NOT NULL UNIQUE,          -- ZAAK-JJJJ-nnnnnn
  zaaktype_identificatie text NOT NULL,
  initiator_bsn text,
  initiator_nnp_id text,
  object_identificatie text,                   -- BAG: verblijfsobject of pand
  registratiedatum date NOT NULL,
  einddatum date,
  resultaat text,                              -- toegekend, afgewezen, verleend, ...
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS zaken.status (
  id bigserial PRIMARY KEY,
  zaak_identificatie text NOT NULL,
  statustype text NOT NULL,                    -- Ontvangen, In behandeling, Afgehandeld
  datum_status_gezet timestamptz NOT NULL,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

-- === Sociaal domein (bijzondere persoonsgegevens, art. 9 AVG) =====================
CREATE SCHEMA IF NOT EXISTS sociaal;

CREATE TABLE IF NOT EXISTS sociaal.wmo_voorziening (
  id bigserial PRIMARY KEY,
  bsn text NOT NULL,
  voorziening text NOT NULL,
  leveringsvorm text NOT NULL,                 -- ZIN, PGB
  startdatum date NOT NULL,
  einddatum date,
  zaak_identificatie text,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sociaal.jeugdhulp_traject (
  id bigserial PRIMARY KEY,
  bsn text NOT NULL,
  soort text NOT NULL,                         -- ambulant, verblijf, jeugdbescherming
  aanbieder text NOT NULL,
  startdatum date NOT NULL,
  einddatum date,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sociaal.participatiewet_uitkering (
  id bigserial PRIMARY KEY,
  bsn text NOT NULL,
  regeling text NOT NULL,                      -- algemene bijstand
  startdatum date NOT NULL,
  einddatum date,
  maandbedrag numeric(8, 2) NOT NULL,
  gewijzigd_op timestamptz NOT NULL DEFAULT now()
);
