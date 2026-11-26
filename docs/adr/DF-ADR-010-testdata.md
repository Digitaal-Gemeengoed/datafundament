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
