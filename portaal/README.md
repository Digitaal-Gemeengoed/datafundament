# Portaal van het Datafundament

Eén ingang voor data-engineers, platformbeheer en privacy (DF-ADR-013):

- **Platform:** of elk onderdeel antwoordt, de versheid per bron, de laatste runs in Dagster;
- **Dataproducten:** alles van bron tot dataproduct, uit Dagster, met de laatste keer bijgewerkt;
- **Toegang tot data:** aanvragen met doel en grondslag, beoordelen door een ander, en de toekenningen als regels voor Trino;
- **Verwijderverzoeken:** een persoon uit het lakehouse halen, met vier ogen, uitgevoerd door de job `verwijderen` in Dagster, met bewijs (DF-ADR-015);
- **Accounts, groepen en rechten, audit, instellingen, profiel:** het fundament.

## Herkomst

Het fundament komt uit het beheerportaal van de Office Assistent, [`oa-beheer`](https://github.com/Digitaal-Gemeengoed/oa-beheer), commit `8ac3a1d` (0.16.0, vóór de gemeenten). Overgenomen: inloggen via Keycloak met PKCE en tweede factor, sessies, noodaccount, audit met hashketen, accounts, groepen, rechten, instellingen, profiel, NL Design System. Weggelaten: wat bij de Office Assistent hoort (metadatamodel, classificatie, anonimiseren). Het ontwerp van de beveiliging staat in [`docs/security.md`](docs/security.md).

Stack: Node 22, Fastify, PostgreSQL (eigen database `df_portaal` op dfc), React met NL Design System.

## Bouwen en testen

```
npm ci
npm run build
TEST_PG_HOST=/tmp npm test     # een PostgreSQL met superuser 'beheer' op poort 55432
```

## Uitrol

Op dfc via `compose/compose.yml` (diensten `portaal-migreer` en `portaal`), achter Caddy op `admin.datafundament.haarlem.dev`. `server/installeer-platform.sh` maakt de database en de geheimen; `server/keycloak.sh` richt Keycloak in en koppelt het portaal. Het noodaccount instellen:

```
sudo docker compose -f /opt/datafundament/compose/compose.yml run --rm portaal-migreer node backend/dist/cli.js nood-instellen
```

## Licentie

EUPL-1.2, zoals `oa-beheer` (zie `LICENSE`). © 2026 Gemeente Haarlem.
