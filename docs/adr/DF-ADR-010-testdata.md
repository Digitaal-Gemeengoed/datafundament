# DF-ADR-010 — Alleen test- en open data: VrijBRP, BAG, CBS

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

De demo heeft een herkenbare gemeentelijke casus nodig: administratieve gegevens gecombineerd met geodata. Echte persoonsgegevens horen niet in een PoC, ook niet op een afgeschermde server.

## Besluit

**Bronnen:**

| Bron | Rol in de demo | Hoe |
|---|---|---|
| Testdata van **VrijBRP** | Administratieve bron (personen, verblijfplaatsen); de bron voor CDC (DF-ADR-006) | In een eigen PostgreSQL-container als "bronsysteem" |
| **BAG** (Kadaster, kosteloos extract of via PDOK) | Adressen, panden en verblijfsobjecten met geometrie | Ingestie met dlt, alleen het gebied van de demo |
| **Wijk- en buurtkaart** en **Kerncijfers wijken en buurten** (CBS, CC-BY) | Buurtgrenzen en kerncijfers als noemer | Ingestie met dlt |
| Zelf gegenereerde **meldingen openbare ruimte** | Een tweede administratieve bron met locatie, om te verrijken | Generator in `bron/`, met een vaste seed |

Mogelijke aanvullingen, nog te bekijken:

- de **Synthetic Data Generator** van Digilab, die een deel van de BRP nabootst met gegevens uit BAG en CBS;
- de downloadbare testomgeving van de **BRP API** (Haal Centraal) met eigen testpersonen;
- **Open Personen**, dat een eigen testset via de BRP API kan leveren.

**Regels:**

- Nooit echte persoonsgegevens. Een BSN is een testnummer uit de testset.
- Testdata die niet openbaar mag, komt niet in de repo. In de repo staat dan alleen een script om haar op te halen of te laden.
- Bij open data staan de bron en de licentie in het dataproduct en in OpenMetadata (naamsvermelding bij CC-BY).

## Gevolgen

- De casus is herkenbaar voor elke gemeente: personen, adressen en meldingen per buurt.
- De gevoelige kolommen in de testset zijn geschikt om maskering in Trino te tonen (DF-ADR-008), zonder dat er iets echts te zien is.
- Open punt: in welke vorm de testdata van VrijBRP beschikbaar is (database-dump, CSV of API), en onder welke voorwaarden.

## Overwogen

- **Alleen zelf gegenereerde data:** volledig in de hand, maar minder overtuigend dan de echte structuur van een BRP-systeem.
- **Geanonimiseerde echte data:** te veel risico en te veel werk voor een PoC.

## Aanvulling (26 november 2026): de testdata van vrijBRP

Een database of dump van vrijBRP zelf staat niet openbaar, en de hele vrijBRP Balie (Java met Tomcat) draaien is te veel werk voor wat de PoC nodig heeft. Wel openbaar, onder de EUPL-1.2: de module `gba-testdata` in [vrijBRP-Balie](https://github.com/vrijBRP/vrijBRP-Balie) (Procura). Daarin staan de testsets van de RvIG en GBA-V en de demopersonen van Procura, als persoonslijsten in de structuur van het LO BRP, met historie.

**Besluit:**

- De bron op dfw is een eigen PostgreSQL-schema dat lijkt op dat van een BRP-systeem: een tabel per categorie, een kolom per rubriek, met historie. Zie [`bron/`](../../bron/README.md).
- Een script laadt de testdata, vastgepind op commit `fb9f41b`, en ontdubbelt op A-nummer: 666 personen, ruim 7.000 rijen, waarvan ongeveer 3.000 historie.
- De testdata komt niet in onze repo; het script haalt haar op.
- Mutaties voor de demo (verhuizen, overlijden, een nieuwe kolom) schrijven in de bron, zodat CDC en schemawijziging live te zien zijn.

**Gevolgen:**

- De personen wonen volgens de testdata vooral in Stichtse Vecht, Den Haag, Rotterdam en Amsterdam, en deels in fictieve testgemeenten van de RvIG. BAG, CBS-buurten en meldingen volgen daarom die gemeenten, niet Haarlem.
- vrijBRP staat in de Softwarecatalogus inmiddels bij Shift2. Wie later een echte vrijBRP-database als bron wil gebruiken, kan daar terecht.
