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

## Aanvulling (26 november 2026): geodata

- **Adressen naar coördinaten:** de actuele adressen uit de ruwe laag worden opgezocht in de PDOK Locatieserver (BAG). Die geeft een punt in RD en de buurtcode. Alleen nieuwe adressen worden opgezocht. Een adres dat niet in de BAG staat (fictief in de testdata), krijgt `gevonden = false`.
- **Buurten:** CBS Wijken en Buurten 2025 via de OGC API van PDOK (CC-BY 4.0), alleen voor de gemeenten die de Locatieserver teruggeeft. Met kerncijfers, zoals het aantal inwoners.
- **Dataproduct:** testpersonen per buurt, naast het aantal inwoners volgens CBS. Het staat in het lakehouse en in PostGIS (met geometrie, sleutel en ruimtelijke index, voor QGIS).
- Een volledige BAG (tientallen GB) is voor de PoC niet nodig.

## Aanvulling (26 november 2026): synthetische gemeentelijke bronnen

De BRP alleen laat te weinig zien van wat een gemeente in haar datawarehouse heeft. Daarom komen er synthetische bronnen bij, elk als eigen schema in de bron op dfw, zoals een eigen applicatie:

| Schema | Wat | Gekoppeld via |
|---|---|---|
| `bag` | woonplaats, openbare ruimte, nummeraanduiding, pand, verblijfsobject | de adressen in de BRP; geldige BAG-identificaties uit de BRP worden overgenomen |
| `woz` | WOZ-object, waarde per peildatum (2021–2025), belanghebbenden | verblijfsobject; eigenaar en gebruiker op BSN, of een verzonnen corporatie of bedrijf |
| `belastingen` | aanslagen OZB en afvalstoffenheffing (2024–2026) | WOZ-object en BSN; kwijtschelding bij lopende bijstand |
| `mor` | 3.000 meldingen openbare ruimte met statusverloop (zoals Signalen) | nummeraanduiding, punt in RD, soms een melder (BSN) |
| `zaken` | zaaktypen, zaken, statusverloop (zoals de ZGW-API's) | BSN of NNP, verblijfsobject of pand; verhuiszaken volgen de BRP |
| `sociaal` | Wmo-voorzieningen, jeugdhulp, Participatiewet | BSN; Wmo-voorzieningen horen bij een Wmo-zaak |

**Besluit:**

- Eén generator (`bron/werkbank/synthetisch.py`) maakt alles uit de BRP met een vaste seed: dezelfde BRP geeft dezelfde data. Er staat geen gegenereerde data in de repo.
- Elke tabel heeft `id` en `gewijzigd_op`, net als de BRP. De ingestie is daarom generiek: één lijst met bronnen in `ingestie/bronnen.py`, per bron de lagen `ruw_<bron>` (insert-only) en `ruw_<bron>_stand` (upsert), en per tabel een asset in Dagster.
- Bewust ingebouwde verschillen tussen BAG en BRP, voor een kwaliteitscontrole in dbt: adres ontbreekt in de BAG, postcode wijkt af, bewoond verblijfsobject is ingetrokken, ongeldige BAG-identificatie in de BRP, leegstaande woningen. De generator meldt hoeveel van elk.
- Coördinaten en panden zijn verzonnen (RD, rond een middelpunt per gemeente). Voor echte locaties blijft de Locatieserver.
- Twee mutaties voor de demo: `bron.sh melding` en `bron.sh zaak-afhandelen`.

**Gevolgen:**

- `sociaal` bevat bijzondere persoonsgegevens (art. 9 AVG), al zijn ze verzonnen. In de PoC staan ze, net als de rest, in de ruwe laag. Het laat zien waar straks toegangsregels (Trino, Keycloak, DF-ADR-012) en maskering in dbt nodig zijn; dat is het eerstvolgende dataproduct op deze bronnen.
- De publicatie `datafundament` omvat de schema's die dfc rechtstreeks leest. Zaken en belastingen komen sinds DF-ADR-014 via een API en een export.
- De ingestie doet veertien dlt-runs in plaats van twee (zeven bronnen, twee lagen). Dat past nog in het schema van vijf minuten; anders gaat de frequentie omlaag.
