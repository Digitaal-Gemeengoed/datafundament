# DF-ADR-003 — Lakekeeper als Iceberg REST-catalogus

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

Het voorstel had geen Iceberg-catalogus. Die is wel nodig:

- DuckDB schrijft alleen naar Iceberg als er een REST-catalogus is aangekoppeld; de catalogus legt de nieuwe metadata vast;
- Trino leest de tabellen ook via die catalogus.

Zonder catalogus zijn er losse Parquet-bestanden, geen tabellen met transacties en historie.

## Besluit

**Lakekeeper** (Apache 2.0, Rust), met een eigen PostgreSQL-database. Versie vastgepind.

- Eén warehouse `datafundament` op Garage, met STS uit (DF-ADR-002).
- Eén catalogus voor alle schrijvers en lezers: dlt, dbt met DuckDB, Trino.
- Inloggen via OAuth2 met Keycloak (DF-ADR-012). Voor de eerste week mag het zonder, alleen binnen het compose-netwerk.

## Gevolgen

- Iceberg-tabellen hebben één bron van waarheid voor schema, snapshots en partities.
- Lakekeeper kan rechten per gebruiker afdwingen, ook vanuit Trino via de Open Policy Agent. Dat gebruiken we pas als het toegangsmodel staat (fase 5).
- Een extra onderdeel om te beheren, maar wel een klein: één binary en een database.

## Overwogen

- **Apache Polaris:** volwassen en breed gedragen, maar Java en zwaarder in beheer.
- **Project Nessie:** catalogus met Git-achtig versiebeheer. Dat is aantrekkelijk, maar dubbelop met Git en met de historie uit DF-ADR-005.
- **SQL-catalogus van PyIceberg op Postgres:** het lichtst, maar geen REST. DuckDB kan er niet naar schrijven.
