# DF-ADR-009 — Eén nieuwe VPS met Docker Compose

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

De PoC krijgt een eigen, nieuwe VPS. De servers van de Office Assistent en het gemeenschapsplatform hebben elk een ander risicoprofiel, en de PoC hoort daar niet bij.

## Besluit

- **Eén VPS**, los van de servers van de Office Assistent en het gemeenschapsplatform, en niet in hun privénetwerk.
- **Docker Compose met profielen:**
  - `kern`: Garage, Lakekeeper, Trino, PostgreSQL met PostGIS, Dagster, de demobronnen;
  - `metadata`: OpenMetadata met zoekindex en database;
  - `portaal`: het portaal (DF-ADR-013) en Keycloak (DF-ADR-012).
- **Grootte:** 8 vCPU en 32 GB geheugen. Met 16 GB past `kern` wel, maar `kern` met `metadata` niet.
- **Caddy** voor TLS en als enige ingang. Van buiten bereikbaar zijn alleen de schermen en Trino, en zolang het een PoC is alleen met wachtwoord of via Keycloak. Dagster heeft in de open-source versie geen eigen inlog en komt achter oauth2-proxy.
- **Uitrol zoals in het gemeenschapsplatform:** de server haalt zelf op uit GitHub, met een systemd-timer, en GitHub komt er niet in. Versies van images worden vastgepind in `compose/`.
- **Lokaal:** `kern` draait ook op een laptop, voor ontwikkelen zonder server.

## Gevolgen

- Eén server is één storingspunt. Voor een PoC is dat aanvaardbaar; er komt een nachtelijke back-up van de databases en van Garage.
- Alle instellingen staan in de repo of in `.env`. Een andere partij kan de server opnieuw opbouwen zonder kennis die alleen bij ons ligt.

## Overwogen

- **Kubernetes:** past bij productie bij een hoster, maar is te veel beheer voor een PoC van één week.
- **Op een bestaande VPS van Digitaal Gemeengoed:** sneller, maar dat mengt risicoprofielen.
