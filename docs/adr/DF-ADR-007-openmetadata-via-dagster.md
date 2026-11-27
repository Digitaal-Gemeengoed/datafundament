# DF-ADR-007 — OpenMetadata-ingestie als job in Dagster, zonder Airflow

- **Status:** aanvaard (uitgevoerd 27 november 2026)
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

Het voorstel spreekt van "twee-richtings metadata-uitwisseling" tussen Dagster en OpenMetadata. De Dagster-connector van OpenMetadata werkt in één richting: OpenMetadata leest pipelines, runs en lineage uit Dagster via GraphQL.

OpenMetadata is ook het zwaarste onderdeel van de stack: een server, een zoekindex, een database, en standaard een eigen container met Airflow om de ingestie te draaien.

## Besluit

- **Geen Airflow.** De ingestie van OpenMetadata (Trino, PostgreSQL, dbt, Dagster) draait als gewone job in Dagster, met de CLI van de ingestie-bibliotheek en configuratie in YAML in `metadata/`.
- **Twee richtingen zijn dan echt:**
  - Dagster stuurt de ingestie aan, na elke geslaagde run van de keten;
  - OpenMetadata leest de metadata en lineage uit Dagster, dbt en Trino.
- **Datakwaliteit:** de tests van dbt komen via de dbt-ingestie (`manifest.json`, `run_results.json`) in OpenMetadata, als testresultaten per tabel.
- **Eerste week:** de lineage tonen we in de asset-graaf van Dagster zelf. OpenMetadata komt erbij als het geheugen van de server dat toelaat (DF-ADR-009).

## Gevolgen

- Eén orkestrator in plaats van twee, en de ingestie staat als code in Git.
- De beheerschermen van OpenMetadata voor het plannen van ingestie werken dan niet; die plannen staan in Dagster.
- De zoekindex van OpenMetadata blijft nodig. Die draait in de eigen compose van OpenMetadata, los van andere onderdelen.

## Overwogen

- **OpenMetadata met de eigen Airflow:** standaard, en plannen kan vanuit de schermen. Maar dan zijn er twee orkestrators en is er meer geheugen nodig.
- **OpenLineage met Marquez:** lichter voor lineage alleen, maar zonder catalogus, kwaliteit en zoekfunctie. Het voorstel vraagt die wel.
- **DataHub:** vergelijkbaar met OpenMetadata, maar zwaarder.

## Uitgevoerd (27 november 2026)

- **OpenMetadata 2.1.1** op dfc, op `metadata.<domein>`. Erbij:
  - **OpenSearch 3.4** als zoekindex: Apache-licentie, alleen binnen het compose-netwerk;
  - **de database** `openmetadata` in de bestaande PostgreSQL;
  - **geen Airflow:** `PIPELINE_SERVICE_CLIENT_ENABLED=false`.
- **Inloggen via Keycloak** (client `df-metadata`, vertrouwelijk). De eerste beheerder is de gebruiker uit `server/keycloak.sh`, het deel vóór de @. Wie in de realm een account heeft, komt binnen als gewone gebruiker.
- **Eigen sleutels.** De RSA-sleutels in het image zijn openbaar: daarmee kan iedereen een token maken. Daarom maakt het installatiescript eigen sleutels (`compose/openmetadata/`, niet in Git), en ook een eigen Fernet-sleutel.
- **De ingestie** is de job `metadata` in Dagster (`orkestratie/metadata.py`), met configuratie in `metadata/`. Na een geslaagde keten draait hij hoogstens één keer per uur. Hij doet:
  1. `dbt docs generate`;
  2. de catalogus uit Trino (catalogi `lakehouse` en `dwh`; alleen metadata, geen voorbeeldrijen of profielen);
  3. dbt: beschrijvingen, lineage en de uitkomst van de laatste `dbt build`, ook als een test faalde;
  4. Dagster: jobs, runs en lineage.

  De bibliotheek van OpenMetadata staat in een eigen virtualenv in het werk-image (`/opt/openmetadata`), want hij heeft andere afhankelijkheden dan Dagster.
- **Eén handmatige stap:** het token van de ingestion-bot. Dat maakt OpenMetadata zelf, en het is alleen als beheerder op te halen. Na de eerste inlog: Settings → Bots → ingestion-bot, en dan `server/metadata-token.sh`. Tot die stap slaat de job over.
- **In het portaal** staat OpenMetadata bij de platformstatus.

**Niet getest** in de sandbox: de server zelf en de inlog via Keycloak, want daar draait geen Docker. Wel gecontroleerd:
- de compose-configuratie;
- de workflows tegen de schema's van `openmetadata-ingestion` 2.1.1;
- de installatie van die bibliotheek op Python 3.13;
- het laden van de Dagster-definities.

De queries van de ingestie gaan door Trino en staan dus ook in het log van de datavragen (DF-ADR-016), als gebruiker `openmetadata`.
