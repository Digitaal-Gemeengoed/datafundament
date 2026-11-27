# DF-ADR-019 — Lakekeeper via Keycloak, met rechten in OpenFGA

- **Status:** aanvaard
- **Datum:** 27 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

Lakekeeper draaide zonder inlog en zonder rechten (`allowall`). Binnen het compose-netwerk kon elk onderdeel elke tabel lezen, wijzigen en weggooien, en Lakekeeper legde niet vast wie dat deed. De web-UI zat wel achter de poort (DF-ADR-018), maar toonde "Authentication is OFF". Voor de security- en privacyteams is dat het verkeerde signaal: de catalogus is de plek waar staat welke tabellen er zijn en waar hun bestanden staan.

Lakekeeper kan zelf inloggen via OpenID Connect en kan rechten bijhouden in OpenFGA. Beide zijn open source.

## Besluit

- **Lakekeeper neemt alleen tokens van Keycloak aan,** met audience `lakekeeper`. Een scope `lakekeeper` in de realm zet die audience in het token.
- **Elk onderdeel heeft een eigen service-account** in Keycloak (client credentials, token een uur geldig):

  | Account | Wie | Rechten op het warehouse `datafundament` |
  |---|---|---|
  | `df-lk-werk` | dlt, dbt (DuckDB), onderhoud, verwijderen | maken en wijzigen (`create`, `modify`) |
  | `df-lk-trino` | Trino | alleen lezen (`select`) |
  | `df-lk-beheer` | `beheer/inrichten.py` | beheerder van de server en het project |

  De rechten gelden voor alles onder het warehouse: namespaces, tabellen en views, ook die van vóór de overstap.
- **De rechten staan in OpenFGA** (v1.14.2), met een eigen database `openfga`. OpenFGA is alleen binnen het netwerk bereikbaar; Lakekeeper meldt zich met een gedeelde sleutel.
- **De web-UI logt in via Keycloak** (client `lakekeeper`, openbaar, met PKCE). De eerste beheerder uit Keycloak wordt beheerder in Lakekeeper. De poort (DF-ADR-018) blijft ervoor staan: alleen wie `platform.bedienen` heeft, komt bij de UI.
- **`beheer/inrichten.py` richt alles in en mag opnieuw draaien.** Het doet de bootstrap als `df-lk-beheer`, meldt de andere accounts aan, maakt het warehouse en zet de rechten. Wat er al is, blijft.
- **Overstap op een draaiende server:** de bestaande objecten gaan naar OpenFGA met `lakekeeper openfga reconcile --mode add-missing`. Lakekeeper was al ingericht, zonder beheerder. Daarom geeft het script dan code 3, en het installatiescript draait `lakekeeper reopen-bootstrap --yes` en daarna het script opnieuw. Data en tabellen blijven staan.

## Gevolgen

- Lakekeeper weet nu wie wat doet. Trino kan in de catalogus niets wijzigen, ook niet bij een fout in de configuratie van Trino.
- **Keycloak hoort nu bij de keten.** Zonder Keycloak geen token, en dan stopt de ingestie. Keycloak draait op dezelfde server; Dagster probeert het bij de volgende run opnieuw.
- **Er komen vier geheimen bij** (drie service-accounts en de sleutel voor OpenFGA), en één dienst: OpenFGA, ongeveer 100 MB geheugen.
- **De rechten van mensen in Lakekeeper staan los van het portaal.** Nu is alleen de eerste beheerder er beheerder. Andere mensen zien in de UI pas iets als een beheerder ze rechten geeft. Dat koppelen aan het portaal staat op de lijst voor later.
- **LoQE (de SQL-editor in de UI) leest nog steeds geen data,** en dat blijft zo (DF-ADR-018): geen CORS en geen vended credentials op Garage.

## Getest

Lokaal, met dezelfde versies van Lakekeeper (0.13.9), OpenFGA en Keycloak, en S3 van moto in plaats van Garage:

- inrichten op een lege catalogus, en twee keer achter elkaar;
- de overstap: een catalogus uit `allowall` met een bestaande tabel, `reconcile`, code 3, `reopen-bootstrap`, opnieuw inrichten. Daarna wijzigt `df-lk-werk` de oude tabel en maakt er een naast, en kan `df-lk-trino` hem lezen maar niet wijzigen;
- pyiceberg en DuckDB (iceberg-extensie, `CREATE SECRET ... TYPE iceberg`) schrijven als `df-lk-werk`; als `df-lk-trino` lezen ze wel en geeft schrijven 403; een verkeerd geheim geeft geen token.

Niet lokaal getest: Trino zelf met OAuth2 naar Lakekeeper, en inloggen in de web-UI. Die blijken bij de uitrol.

## Overwogen

- **Alleen inloggen, zonder OpenFGA** (`allowall` met tokens): Lakekeeper weet wie er komt, maar iedereen mag alles. Het grootste risico, Trino of een fout script dat wijzigt, blijft dan.
- **Rechten van mensen uit het portaal naar OpenFGA schrijven,** zoals bij Trino (DF-ADR-017): later. Nu werkt alleen de beheerder in de UI, en data lezen loopt via Trino.
- **Niets doen; de poort is genoeg:** de poort beschermt alleen de UI, niet de API binnen het netwerk.
