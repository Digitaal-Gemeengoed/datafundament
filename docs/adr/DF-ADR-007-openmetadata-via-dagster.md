# DF-ADR-007 — OpenMetadata-ingestie als job in Dagster, zonder Airflow

- **Status:** aanvaard
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
