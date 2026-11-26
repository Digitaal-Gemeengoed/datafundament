# DF-ADR-002 — Garage als S3-opslag, niet MinIO

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

Het voorstel noemde MinIO. De community-editie van MinIO is niet meer bruikbaar als open-source basis:

- in mei 2025 verdwenen het beheer en het inloggen via LDAP en OIDC uit de community-editie;
- sinds oktober 2025 publiceert MinIO geen images en binaries meer;
- in december 2025 ging de repository in onderhoudsmodus, en in 2026 is hij gearchiveerd.

De opvolger AIStor is een gesloten product. Voor een PoC die open en soeverein moet zijn, valt MinIO daarmee af.

Binnen Digitaal Gemeengoed draaien al twee opvolgers:

- **Garage** (Deuxfleurs, AGPLv3, Rust) in het gemeenschapsplatform, voor `dg-documenten`;
- **SILO**, de voortzetting van MinIO, in het platform van de Office Assistent (OA-ADR-006), omdat dat Object Lock nodig heeft.

## Besluit

**Garage**, op één node zonder replicatie, net als in het gemeenschapsplatform. De versie wordt vastgepind en pas bijgewerkt na het lezen van de release notes.

- Alleen bereikbaar binnen het compose-netwerk, met `path-style`-adressen.
- **Een eigen sleutel per onderdeel:** dlt en dbt krijgen een sleutel die mag schrijven, Trino een sleutel die alleen mag lezen.
- De back-up is de tweede kopie.

## Gevolgen

- Garage kent geen STS. Lakekeeper kan dus geen kortlevende sleutels uitgeven (*vended credentials*), en de onderdelen krijgen elk een vaste sleutel uit de omgeving. Of *remote signing* van Lakekeeper werkt met DuckDB en Trino op Garage, testen we in de eerste week.
- Garage heeft geen Object Lock. Iceberg heeft dat niet nodig. Moeten bewaartermijnen later in de opslag worden afgedwongen, dan is SILO de kandidaat.
- Omdat alles alleen de S3-API gebruikt, is de opslag vervangbaar. Dat kan in de demo ook getoond worden.

## Overwogen

- **SILO:** zelfde S3-API en schijfformaat als MinIO, met Object Lock. Maar het is een jonge fork met een kleine beheerder, en Object Lock is hier niet nodig.
- **SeaweedFS** (Apache 2.0): heeft eigen Iceberg-functies, maar is een extra onderdeel dat nog nergens binnen Digitaal Gemeengoed draait.
- **AIStor:** gesloten licentie, niet mee te leveren.
