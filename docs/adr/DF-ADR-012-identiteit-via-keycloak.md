# DF-ADR-012 — Identiteit via een eigen Keycloak

- **Status:** voorgesteld
- **Datum:** 26 november 2026
- **Voorgesteld door:** Claude, voor Erik Hoekstra

## Context

Trino, Lakekeeper, OpenMetadata, Dagster (via oauth2-proxy) en het portaal hebben allemaal een inlog nodig. Zonder gedeelde identiteit krijgt elk onderdeel eigen accounts, en is "wie vroeg wat op" in het log van Trino niet te koppelen aan een persoon.

Binnen Digitaal Gemeengoed is het patroon al: Keycloak voor identiteit, per risicoprofiel een eigen Keycloak (realm `gemeenten` voor de Office Assistent, realm `gemeenschap` voor het gemeenschapsplatform).

## Voorstel

- **Een eigen Keycloak op de VPS van de PoC**, realm `datafundament`. Geen koppeling met de realms van de Office Assistent of het gemeenschapsplatform.
- **Clients:** `trino`, `lakekeeper`, `openmetadata`, `dagster` (via oauth2-proxy) en `portaal`, en serviceaccounts voor dlt, dbt en Dagster.
- **Groepen = rollen in de PoC:**
  - `/rol/afnemer`: lezen via Trino, binnen de regels;
  - `/rol/data-engineer`: pipelines en modellen, Dagster bedienen, OpenMetadata bewerken;
  - `/rol/platformbeheer`: alles, ook gebruikers en regels.
- **Tweede factor verplicht** voor `data-engineer` en `platformbeheer`.
- De realm staat als JSON in de repo en wordt bij elke uitrol gelijkgetrokken, zoals in het gemeenschapsplatform.
- **Fasering:** in de eerste week een gedeeld wachtwoord via Caddy; Keycloak komt in fase 5.

## Gevolgen

- Eén persoon is in elk onderdeel dezelfde persoon, en het log van Trino noemt die persoon.
- Later kan een gemeente haar eigen inlog koppelen (bijvoorbeeld Entra ID) via brokering.
- Een extra onderdeel met een eigen database.

## Overwogen

- **De Keycloak van het gemeenschapsplatform hergebruiken:** minder beheer, maar dan hangt toegang tot data af van een platform met vrije registratie.
- **Alleen lokale accounts per onderdeel:** snel, maar het log en het toegangsmodel worden dan onbetrouwbaar.
