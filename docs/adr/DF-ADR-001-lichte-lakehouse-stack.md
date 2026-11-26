# DF-ADR-001 — Een lichte lakehouse-stack zonder Spark

- **Status:** aanvaard. De keuze voor MinIO is vervangen door [DF-ADR-002](DF-ADR-002-garage-als-s3-opslag.md); de catalogus is aangevuld in [DF-ADR-003](DF-ADR-003-lakekeeper-als-iceberg-catalogus.md).
- **Datum:** 26 november 2026
- **Besloten door:** Fabien (voorstel), Erik Hoekstra

## Context

De PoC moet laten zien dat een lichte open-source stack genoeg is voor een open, metadatagedreven data lakehouse. De hoeveelheden data zijn overzichtelijk en het werk is vooral batchverwerking, ook van geodata. Zware clusters zoals Spark zijn dan meer last dan nut.

## Besluit

| Domein | Onderdeel |
|---|---|
| Ontsluiting en CDC | dlt (data load tool) |
| Validatie, uniformering en dataproductie | dbt Core met DuckDB, ook de extensie `spatial` |
| Ruwe en uniforme opslag | Apache Iceberg |
| Opslag van dataproducten | PostgreSQL met PostGIS |
| Voordeur voor afnemers | Trino |
| Orkestratie | Dagster |
| Metadata en lineage | OpenMetadata |
| Objectopslag | S3 (zie DF-ADR-002) |
| Ontwikkeling | Git: pipelines, modellen, regels en flows als code |

Afnemers (BI, GIS, analisten) komen alleen via Trino binnen (DF-ADR-008). dbt met DuckDB doet het zware werk; Trino leest en ontsluit alleen.

## Gevolgen

- Alle logica staat in SQL en Python, niet in een product. Een ander team kan het lezen en overnemen.
- DuckDB draait binnen het proces: snel en lokaal te testen, maar het schaalt niet over meerdere machines. Voor de hoeveelheden van één gemeente is dat geen bezwaar.
- De PoC richt zich op de kern. Een API-gateway, uitgebreide beleidsregels en streaming horen er niet bij, maar kunnen later worden toegevoegd.

## Overwogen

- **Spark met Iceberg:** de gangbare keuze voor grote volumes, maar te zwaar in beheer voor deze schaal.
- **Alleen PostgreSQL:** eenvoudiger, maar zonder open tabelformaat en scheiding van opslag en rekenkracht. Dan is het geen lakehouse.
