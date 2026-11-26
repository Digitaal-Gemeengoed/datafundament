# DF-ADR-004 — Schrijven naar Iceberg met dbt en DuckDB, met dbt-trino als terugval

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

dbt met DuckDB moet de uniforme laag en de dataproducten naar Iceberg schrijven. DuckDB kan dat sinds versie 1.4: invoegen sinds 1.4.0, bijwerken en verwijderen sinds 1.4.2, altijd via een REST-catalogus. Maar:

- DuckDB noemt de Iceberg-extensie zelf nog experimenteel;
- bijwerken en verwijderen gaat alleen als *merge-on-read*;
- het geometrietype `GEOGRAPHY` van Iceberg wordt niet ondersteund.

Dit is het grootste technische risico van de stack.

## Besluit

1. **In de eerste week testen** we het hele pad: dbt-duckdb → DuckDB → Lakekeeper → Garage, met invoegen, `MERGE` en schemawijziging. Daarna lezen we hetzelfde met Trino.
2. **Terugval:** lukt dat niet betrouwbaar, dan schrijft **dbt-trino** de lagen in Iceberg, en blijft DuckDB voor lokaal ontwikkelen en testen. De dbt-modellen blijven SQL; alleen de adapter verandert.
3. **Geodata:**
   - in Iceberg als **WKB** in een binaire kolom, met het coördinatenstelsel (EPSG:28992) in de kolombeschrijving;
   - als echte geometrie pas in **PostGIS**, met ruimtelijke indexen;
   - in DuckDB en Trino omzetten met `ST_GeomFromWKB`.

## Gevolgen

- Een tegenvaller ontdekken we op dag 1 of 2, niet tijdens de demo.
- Geodata in Iceberg is opslag, geen ruimtelijke database. Ruimtelijke vragen gaan naar PostGIS, of zetten WKB eerst om.
- Met de terugval doet Trino ook schrijfwerk. Dat raakt de scheiding uit DF-ADR-001 (Trino leest alleen). Dan krijgt Trino een aparte schrijfgebruiker, los van de afnemers.

## Overwogen

- **PyIceberg vanuit Python:** werkt, maar dan staat de transformatielogica in Python in plaats van in dbt-SQL.
- **Wachten op Iceberg v3-geometrie** in alle engines: niet binnen de looptijd van de PoC.

## Uitkomst van de proef (26 november 2026)

De proef in [`proeven/iceberg-schrijfpad`](../../proeven/iceberg-schrijfpad/README.md) is op dfc **geheel geslaagd**:

- Lakekeeper maakte het warehouse op Garage aan, zonder STS en zonder remote signing, en controleerde zelf of schrijven en lezen werkten.
- DuckDB maakte een tabel en voerde invoegen (met geometrie als WKB), `UPDATE`, `DELETE`, `MERGE INTO`, een nieuwe kolom en weer invoegen uit. Het resultaat klopte, met 5 snapshots.
- Trino las dezelfde tabel terug: met de wijzigingen van DuckDB (ook de verwijderingen als *positional deletes*), de nieuwe kolom, de geometrie uit WKB en de snapshots.

Gebruikte versies, die we vastpinnen:

| Onderdeel | Versie |
|---|---|
| Garage | `dxflrs/garage:v2.5.0` |
| Lakekeeper | 0.13.9 (`vakamo/lakekeeper@sha256:e5a0e9d3ffecf0c09b2c0bcd2258e9adc2274bf88c1127b2ca08ea02966b5f48`) |
| Trino | 484 (`trinodb/trino@sha256:2704eb53935af5e582d63d6033e9bf99d20c325e9b0e30b1016ef59a4773979f`) |
| DuckDB | 2.0.1 |

**Gevolg:** de terugval op dbt-trino is voorlopig niet nodig. Nog te bewijzen: hetzelfde pad met dbt-duckdb ertussen, en schrijven vanuit dlt.
