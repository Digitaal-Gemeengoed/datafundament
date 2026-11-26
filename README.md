# Datafundament

**Proof of concept voor een open-source data lakehouse** voor gemeenten: licht, metadatagedreven en volledig als code.

> In opbouw. Een PoC, geen product.

## Wat de PoC laat zien

1. **De architectuur in samenhang.** Een draaiende omgeving waarin ingestie, opslag, verwerking, voordeur, orkestratie en metadata echt samenwerken.
2. **Een end-to-end casus.** Administratieve gegevens (testdata van VrijBRP en meldingen openbare ruimte) gecombineerd met geodata (BAG, CBS-buurten), van bron tot dataproduct. De tussenstappen, kwaliteitsregels en lineage zijn onderweg te volgen.

## Stack

| Rol | Onderdeel | ADR |
|---|---|---|
| Ontsluiting en CDC | dlt | [001](docs/adr/DF-ADR-001-lichte-lakehouse-stack.md), [006](docs/adr/DF-ADR-006-cdc-in-de-poc.md) |
| Validatie, uniformering, dataproductie | dbt Core met DuckDB | [004](docs/adr/DF-ADR-004-schrijfpad-naar-iceberg.md) |
| Ruwe en uniforme opslag, met historie | Apache Iceberg, SCD2 | [005](docs/adr/DF-ADR-005-historie-met-scd2.md) |
| Iceberg-catalogus | Lakekeeper | [003](docs/adr/DF-ADR-003-lakekeeper-als-iceberg-catalogus.md) |
| Objectopslag | Garage (S3) | [002](docs/adr/DF-ADR-002-garage-als-s3-opslag.md) |
| Dataproducten | PostgreSQL met PostGIS | [001](docs/adr/DF-ADR-001-lichte-lakehouse-stack.md) |
| Voordeur voor afnemers | Trino | [008](docs/adr/DF-ADR-008-trino-enige-voordeur.md) |
| Orkestratie | Dagster | [001](docs/adr/DF-ADR-001-lichte-lakehouse-stack.md) |
| Metadata, lineage, kwaliteit | OpenMetadata | [007](docs/adr/DF-ADR-007-openmetadata-via-dagster.md) |
| Identiteit | Keycloak *(voorgesteld)* | [012](docs/adr/DF-ADR-012-identiteit-via-keycloak.md) |
| Portaal | op het fundament van oa-beheer *(voorgesteld)* | [013](docs/adr/DF-ADR-013-portaal-op-fundament-oa-beheer.md) |

Alle besluiten: [`docs/adr/`](docs/adr/README.md).

## Mappen (gepland)

```
compose/          Docker Compose met profielen: kern, metadata, portaal
bron/             demobronnen: VrijBRP-testdatabase, generator voor meldingen
ingestie/         dlt-pipelines
transformatie/    dbt-project (uniforme laag, dataproducten, tests, snapshots)
orkestratie/      Dagster-definities
datahub/trino/    catalogi, regels voor toegang, event listener
metadata/         ingestie-configuratie voor OpenMetadata
portaal/          portaal voor data-engineers en platformbeheer (later)
server/           inrichten en bijwerken van de VPS
demo/             draaiboek en scripts voor de demo
docs/adr/         architectuurbesluiten
```

## Eerste week

| Dag | Doel |
|---|---|
| 1 | Compose `kern` draait lokaal. **Tests:** dbt-duckdb → Lakekeeper → Garage (DF-ADR-004), remote signing of vaste sleutels (DF-ADR-002) |
| 2 | Bronnen: VrijBRP-testdata in Postgres met logische replicatie; BAG en CBS voor het demogebied. dlt laadt de ruwe laag met SCD2 |
| 3 | dbt: uniforme laag, kwaliteitstests, snapshots, dataproduct "meldingen per buurt" naar PostGIS en terug naar Iceberg. **Test:** QGIS via Trino (DF-ADR-008) |
| 4 | Dagster stuurt de keten; schema drift en CDC live te tonen. VPS ingericht, Caddy met wachtwoord ervoor |
| 5 | OpenMetadata als het geheugen het toelaat (anders lineage in Dagster). Draaiboek voor de demo |

Na de eerste week: OpenMetadata volledig, Keycloak en regels in Trino (maskering, log), het portaal.

## Licentie

Zie `LICENSE`.

Gemaakt binnen Digitaal Gemeengoed door Erik Hoekstra, met Fabien, en met assistentie van Claude (Anthropic). Zie [DF-ADR-011](docs/adr/DF-ADR-011-ai-als-versneller.md).
