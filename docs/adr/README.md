# Architectuurbesluiten (ADR's)

Elk besluit over de architectuur van het Datafundament staat hier in een eigen bestand. Het voorvoegsel **DF** voorkomt botsingen met de ADR's van de Office Assistent (OA), XENA en OpenDOP.

## Vorm

Elk ADR heeft:

- **Status:** *voorgesteld*, *aanvaard*, *vervangen door DF-ADR-xxx* of *vervallen*.
- **Datum** en **wie besliste**.
- **Context:** waarom er iets te beslissen viel.
- **Besluit:** wat we doen.
- **Gevolgen:** wat dat oplevert en wat het kost.
- **Overwogen:** de alternatieven, en waarom die het niet werden.

Een besluit wordt niet herschreven. Verandert het, dan komt er een nieuw ADR, en het oude krijgt de status *vervangen door*.

## Overzicht

| Nr | Besluit | Status |
|---|---|---|
| [001](DF-ADR-001-lichte-lakehouse-stack.md) | Een lichte lakehouse-stack zonder Spark | aanvaard |
| [002](DF-ADR-002-garage-als-s3-opslag.md) | Garage als S3-opslag, niet MinIO | aanvaard |
| [003](DF-ADR-003-lakekeeper-als-iceberg-catalogus.md) | Lakekeeper als Iceberg REST-catalogus | aanvaard |
| [004](DF-ADR-004-schrijfpad-naar-iceberg.md) | Schrijven naar Iceberg met dbt en DuckDB, met dbt-trino als terugval | aanvaard |
| [005](DF-ADR-005-historie-met-scd2.md) | Historie met SCD2, niet met time travel | aanvaard |
| [006](DF-ADR-006-cdc-in-de-poc.md) | CDC in de PoC alleen op een Postgres-bron | aanvaard |
| [007](DF-ADR-007-openmetadata-via-dagster.md) | OpenMetadata-ingestie als job in Dagster, zonder Airflow | aanvaard |
| [008](DF-ADR-008-trino-enige-voordeur.md) | Trino als enige voordeur; QGIS eerst testen | aanvaard, met open punt |
| [009](DF-ADR-009-twee-vps-platform-en-bron.md) | Twee VPS'en: platform en bron, verbonden via WireGuard | aanvaard |
| [010](DF-ADR-010-testdata.md) | Alleen test- en open data: VrijBRP, BAG, CBS | aanvaard |
| [011](DF-ADR-011-ai-als-versneller.md) | AI als versneller; het resultaat is gewone, leesbare code | aanvaard |
| [012](DF-ADR-012-identiteit-via-keycloak.md) | Identiteit via een eigen Keycloak | aanvaard |
| [013](DF-ADR-013-portaal-op-fundament-oa-beheer.md) | Een portaal op het fundament van oa-beheer | aanvaard |
| [014](DF-ADR-014-simulatie-en-drie-ingestiepatronen.md) | Een gesimuleerd jaar, en drie manieren waarop data binnenkomt | aanvaard |
| [015](DF-ADR-015-pseudonimisering-en-verwijderen.md) | Pseudoniemen bij de poort, een sleutelkluis, en verwijderen met crypto-shredding | aanvaard |
| [016](DF-ADR-016-elke-datavraag-vastleggen.md) | Elke datavraag vastleggen, door Trino zelf | aanvaard |
