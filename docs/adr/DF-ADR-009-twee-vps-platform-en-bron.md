# DF-ADR-009 — Twee nieuwe VPS'en: platform en bron, met Docker Compose

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

De PoC krijgt eigen, nieuwe servers. De servers van de Office Assistent en het gemeenschapsplatform hebben elk een ander risicoprofiel, en de PoC hoort daar niet bij.

Bij een gemeente staat een bronsysteem nooit op de server van het lakehouse. De bron bevat (test)persoonsgegevens; het lakehouse bevat verwerkte dataproducten. CDC over het netwerk, vanaf een ander systeem, laat ook meer zien dan replicatie binnen één machine.

Geschat geheugengebruik van het platform:

| Wat | Geheugen |
|---|---|
| `kern`: Trino, Garage, Lakekeeper, PostGIS, Dagster, DuckDB tijdens een dbt-run | ± 12–14 GB |
| `metadata`: OpenMetadata met zoekindex en database | ± 8 GB |
| `portaal`: Keycloak, portaal, oauth2-proxy, Caddy | ± 2 GB |

## Besluit

**Twee VPS'en**, los van de servers van de Office Assistent en het gemeenschapsplatform, en niet in hun privénetwerk:

| Server | Wat | Grootte | Privénetwerk | WireGuard |
|---|---|---|---|---|
| **dfc** (Datafundament Core): platform | `kern`, `metadata` en `portaal` | Cloud VPS 12: 12 vCPU, 48 GB geheugen, 200 GB NVMe | 10.0.24.2 | 10.67.0.1 |
| **dfw**: bron | het bronsysteem: PostgreSQL met de testdata van VrijBRP (DF-ADR-010), met logische replicatie (DF-ADR-006) | Cloud VPS 6: 6 vCPU, 12 GB geheugen | 10.0.24.1 | 10.67.0.2 |

Het WireGuard-netwerk 10.67.0.0/24 is bewust anders dan dat van de Office Assistent (10.66.0.0/24).

- **Netwerk:** de twee servers praten via het private netwerk van de provider, met **WireGuard** daarover. Het private netwerk houdt het verkeer van het internet af; WireGuard versleutelt het en maakt ons onafhankelijk van de provider (zoals bij de Office Assistent). De poort van PostgreSQL op de bron luistert alleen op het WireGuard-adres, en de firewall laat alleen de platformserver toe. Docker gaat langs ufw heen; daarom een filter per poort, zoals `docker-filter.sh` in `oa-uitrol`.
- **Docker Compose met profielen** op het platform: `kern`, `metadata`, `portaal`. Op de bron een eigen, kleine compose.
- **Caddy** op het platform voor TLS en als enige ingang. Van buiten bereikbaar zijn alleen de schermen en Trino, en zolang het een PoC is alleen met wachtwoord of via Keycloak. Dagster heeft in de open-source versie geen eigen inlog en komt achter oauth2-proxy. De bron is van buiten niet bereikbaar, behalve SSH.
- **Uitrol zoals in het gemeenschapsplatform:** elke server haalt zelf op uit GitHub, met een systemd-timer, en GitHub komt er niet in. Versies van images worden vastgepind in `compose/`.
- **Lokaal:** `kern` en de bron draaien ook samen op een laptop, voor ontwikkelen zonder server.

## Gevolgen

- Met 48 GB is er ruimte om `kern` en `metadata` tegelijk te laten draaien, ook tijdens een dbt-run en een vraag in Trino. Met 24 GB (Cloud VPS 8) zou dat op de rand zitten.
- Het platform is één storingspunt. Voor een PoC is dat aanvaardbaar. Er komt een nachtelijke back-up van de databases en van Garage, en vóór elke grote wijziging een snapshot van de provider.
- De profielen houden splitsen later eenvoudig. In productie ligt een scheiding van opslag, rekenkracht en governance voor de hand.
- Bij deze prijsklasse wordt processorkracht vaak gedeeld met andere klanten. Voor de PoC is dat geen bezwaar, maar metingen aan prestaties zeggen dan weinig.
- De prijzen gelden de eerste 24 maanden: samen € 26,00 per maand zonder btw (VPS 12 en VPS 6). Daarna gelden de normale prijzen.
- Alle instellingen staan in de repo of in `.env`. Een andere partij kan de servers opnieuw opbouwen zonder kennis die alleen bij ons ligt.

## Overwogen

- **Alles op één server, ook de bron:** eenvoudiger, maar de demo is dan minder geloofwaardig en de risicoprofielen lopen door elkaar.
- **Het platform ook splitsen**, bijvoorbeeld OpenMetadata op een eigen server: betere scheiding, maar elke verbinding tussen servers vraagt inloggen, TLS en firewallregels. Dat is werk dat in één week niets laat zien.
- **Alleen het private netwerk, zonder WireGuard:** minder werk, maar het verkeer is dan onversleuteld op het netwerk van de provider.
- **Alleen WireGuard over het internet, zonder private netwerk:** werkt ook, maar dan staat de poort van WireGuard open naar het internet.
- **Kubernetes:** past bij productie bij een hoster, maar is te veel beheer voor een PoC van één week.
- **Op een bestaande VPS van Digitaal Gemeengoed:** sneller, maar dat mengt risicoprofielen.
