# DF-ADR-008 — Trino als enige voordeur; QGIS eerst testen

- **Status:** aanvaard, met open punt (toegang voor GIS)
- **Datum:** 26 november 2026
- **Besloten door:** Fabien (voorstel), Erik Hoekstra

## Context

Afnemers (BI-tools, QGIS, analisten) mogen nooit rechtstreeks bij Garage, Iceberg of PostGIS. Alles loopt via Trino, zodat autorisatie, het vastleggen van elke datavraag en het combineren van Iceberg en PostGIS op één plek geregeld zijn.

Voor zover bekend heeft QGIS geen ingebouwde koppeling met Trino. Juist GIS-gebruikers, voor wie de geodata bedoeld is, zouden dan buiten de voordeur om moeten.

## Besluit

- **Trino is de enige weg voor afnemers.** Catalogi: `lakehouse` (Iceberg via Lakekeeper) en `dwh` (PostGIS).
- **Rechten:** regels in Trino op catalogus-, schema-, tabel- en kolomniveau, met maskering van kolommen. In de PoC als bestand in Git (`datahub/trino/regels.json`); later eventueel via OPA.
- **Vastleggen:** de HTTP event listener van Trino stuurt elke vraag (wie, wat, wanneer, welke tabellen, resultaat) naar een kleine ontvanger, die haar in een eigen tabel in PostgreSQL zet. Die tabel is via Trino op te vragen, alleen voor beheerders. Trino heeft geen ingebouwde listener voor PostgreSQL; de ontvanger is een paar tientallen regels Python.
- **Open punt, QGIS:** in de eerste week testen we hoe QGIS bij geodata komt via Trino. Daarna kiezen we één van:
  1. een koppeling via JDBC of ODBC, als QGIS daarmee geometrie goed toont;
  2. een dunne OGC API Features-dienst (bijvoorbeeld pygeoapi) die via Trino leest, zodat de regels en het log blijven gelden;
  3. een alleen-lezen PostGIS-rol voor GIS, als bewuste uitzondering met een eigen log. Dan komt er een nieuw ADR.

## Gevolgen

- Eén plek voor toegang en één log van alle vragen.
- Wachtwoorden en OAuth2 in Trino werken alleen via HTTPS. Trino staat daarom achter Caddy, met TLS.
- Trino schrijft niet voor afnemers. Schrijven doen dbt en dlt (DF-ADR-004).

## Overwogen

- **Een eigen API per dataproduct:** meer maatwerk, en het voorstel wil dat juist vermijden.
- **Rechtstreekse toegang tot PostGIS voor GIS:** werkt meteen, maar dan zijn er twee voordeuren. Dat blijft alleen de terugval onder optie 3.
