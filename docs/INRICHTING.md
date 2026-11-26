# De twee servers inrichten, stap voor stap

Dit is de basis: bijwerken, beheerder, firewall, SSH dicht, Docker en een versleuteld netwerk tussen de twee servers. Daarna komt de software (compose), in een volgende stap. Reken op een uur, waarvan veel wachten.

De werkwijze en de scripts komen uit [`oa-uitrol`](https://github.com/Digitaal-Gemeengoed/oa-uitrol/blob/main/server/INRICHTING.md), aangepast voor twee servers (DF-ADR-009).

| Server | Rol | Publiek adres | Privénetwerk | WireGuard | Open op internet |
|---|---|---|---|---|---|
| **dfc** (Datafundament Core, Cloud VPS 12) | platform: het lakehouse, Caddy | 207.180.253.52 | 10.0.24.2 | 10.67.0.1 | SSH, HTTP, HTTPS |
| **dfw** (Cloud VPS 6) | bron: PostgreSQL met de testdata van VrijBRP | 164.68.127.248 | 10.0.24.1 | 10.67.0.2 | alleen SSH |

WireGuard loopt over het privénetwerk van de provider. Het privénetwerk is afgeschermd maar niet versleuteld; WireGuard versleutelt en laat alleen de andere server toe. De WireGuard-poort gaat niet open op internet. Het netwerk 10.67.0.0/24 is bewust anders dan dat van de Office Assistent (10.66.0.0/24).

## 0. Wat je klaar moet hebben

- De **root-wachtwoorden** van dfc en dfw (uit de mail van de provider).
- Je **SSH-sleutel**. Heb je er nog geen, zie stap 1 van de inrichting in `oa-uitrol`.
- Een **wachtwoordmanager**, voor het sudo-wachtwoord van `beheer`.
- **Kladblok**, voor de twee koppelregels.

Beide servers draaien Ubuntu 24.04.

## 1. Inloggen en de repo ophalen (op beide servers)

```
ssh root@207.180.253.52        # dfc
ssh root@164.68.127.248        # dfw
```

Dan op elke server:

```
git clone https://github.com/Digitaal-Gemeengoed/datafundament /opt/datafundament
```

> Zolang de scripts nog niet op `main` staan, gebruik je de branch:
> `git clone --branch server-inrichting https://github.com/Digitaal-Gemeengoed/datafundament /opt/datafundament`
>
> Wordt de repo privé, dan heeft de server een *deploy key* nodig om te kunnen ophalen. Dat komt bij de uitrol (de server haalt zelf op uit GitHub).

## 2. De basis (op beide servers, als root)

```
/opt/datafundament/server/inrichten.sh
```

- Op **dfc** kies je **1** (platform), op **dfw** **2** (bron).
- Het script vraagt een wachtwoord voor de gebruiker `beheer` (voor `sudo`). Bewaar het in je wachtwoordmanager.
- Aan het eind staat een **koppelregel** (`DF-KOPPEL …`). Kopieer die van elke server naar Kladblok. Er staat geen geheim in, alleen de publieke WireGuard-sleutel.

Wat het script doet: alles bijwerken; de gebruiker `beheer` met je SSH-sleutel; de firewall (op dfc SSH, HTTP en HTTPS; op dfw alleen SSH); fail2ban; strengere netwerkinstellingen; dagelijkse beveiligingsupdates met zo nodig een herstart om 04:30; 4 GB wisselgeheugen; Docker met een filter op containerpoorten; een WireGuard-sleutel.

## 3. SSH dichtzetten (op beide servers)

Log in een **nieuw venster** in als `beheer`:

```
ssh beheer@207.180.253.52      # of 164.68.127.248
sudo /opt/datafundament/server/ssh-afsluiten.sh
```

Het script controleert eerst dat je met je sleutel bent ingelogd; zo kun je jezelf niet buitensluiten. Test daarna in nog een venster dat `ssh beheer@…` werkt en `ssh root@…` geweigerd wordt. Meldt het script een nieuwe kernel: `sudo reboot`.

## 4. Koppelen (op beide servers)

Op **dfc**:

```
sudo /opt/datafundament/server/koppelen.sh
```

Plak de koppelregel van **dfw**.

Op **dfw**:

```
sudo /opt/datafundament/server/koppelen.sh
```

Plak de koppelregel van **dfc**. Na de tweede server melden beide dat de ander bereikbaar is.

## 5. Controleren (op beide servers)

```
sudo /opt/datafundament/server/controleer.sh
```

Dit loopt SSH, firewall, WireGuard, de verbinding met de andere server, Docker en het poortfilter na. Het verandert niets.

## 6. De bron starten (op dfw)

```
cd /opt/datafundament/bron
sudo ./bron.sh start
sudo ./bron.sh laden
sudo ./bron.sh status
```

Zie [`bron/README.md`](../bron/README.md). De bron luistert alleen op 10.67.0.2 en laat alleen dfc toe.

## Daarna

- **DNS:** het domein is `datafundament.haarlem.dev`. Twee A-records, beide naar 207.180.253.52 (dfc):
  - `datafundament.haarlem.dev`
  - `*.datafundament.haarlem.dev`

  Caddy haalt per naam een certificaat op. De namen: `datafundament.` (startpagina, later het portaal), `dagster.`, `metadata.` (OpenMetadata), `catalogus.` (Lakekeeper), `trino.` en `id.` (Keycloak). dfw krijgt geen publieke naam.
- **Software:** de compose-bestanden voor dfc (`kern`, `metadata`, `portaal`) en dfw (de bron) volgen, met een script dat ze installeert en bijwerkt.
