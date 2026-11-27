# DF-ADR-016 — Elke datavraag vastleggen, door Trino zelf

- **Status:** aanvaard
- **Datum:** 27 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

Trino is de enige voordeur (DF-ADR-008). Dat heeft pas waarde als ook vastligt wie er door die deur ging, wanneer, en wat er werd opgevraagd. Een gemeente moet kunnen laten zien wie welke persoonsgegevens heeft ingezien: bij een verzoek van een betrokkene (AVG art. 15), bij een datalek, en voor de BIO. De web-UI van Trino toont alleen de laatste queries, en alleen zolang Trino draait.

## Besluit

- **Trino legt het zelf vast.** De HTTP event listener die in Trino zit, stuurt na elke query een `QueryCompletedEvent` (JSON) naar een ontvanger in het portaal. Geen tweede client die meeleest; wat Trino uitvoert, meldt Trino.
- **De ontvanger** draait in het proces van het portaal, op een eigen poort (4301) binnen het compose-netwerk, niet via Caddy. Hij vraagt een gedeeld token (`DATAVRAGEN_TOKEN`, kop `X-Datavragen-Token`, met een vergelijking in constante tijd). Gaat het afleveren mis, dan probeert Trino het tot vijf keer opnieuw. Een query die twee keer aankomt, wordt één keer bewaard (uniek query-id).
- **Wat we bewaren**, in de tabel `datavragen` van het portaal:
  - de gebruiker, de client (bijvoorbeeld DBeaver) en het IP-adres;
  - het soort vraag en de status, met de foutmelding als het misging;
  - de SQL, tot 100.000 tekens;
  - de tabellen en kolommen die werden gelezen;
  - het aantal rijen en bytes;
  - begin en einde.
- **Niets is achteraf te wijzigen.** De database weigert UPDATE, DELETE en TRUNCATE, ook voor de eigenaar. De app-rol mag alleen toevoegen en lezen.
- **In het portaal** staat een pagina Datavragen, met het recht `datavragen.view`. Dat recht geeft alleen door wie het zelf heeft. Je zoekt op gebruiker, tabel, periode en status, en ziet de volledige SQL.

## Gevolgen

- Op de vraag "wie heeft `uniform.persoon` gelezen, en welke kolommen?" is nu een antwoord, voor elke query vanaf de uitrol.
- **Wie de gebruiker is:** zolang Trino geen eigen inlog heeft, staat er de naam die de client opgeeft, achter het ene wachtwoord van Caddy. Pas met Trino via Keycloak (DF-ADR-012) is de gebruiker een geverifieerde persoon. Tot dan is het log volledig in wát er werd gevraagd, maar niet betrouwbaar in wíe.
- **De SQL kan zelf gevoelig zijn**, bijvoorbeeld een WHERE op een pseudoniem. Daarom het aparte recht, en daarom alleen in het portaal te zien.
- **Bewaartermijn:** voorlopig onbeperkt. Een termijn (bijvoorbeeld een jaar, daarna alleen de samenvatting) hoort bij een besluit over bewaren in het algemeen.
- **Queries van het platform zelf**, zoals dbt en de onderhoudsjob, gaan niet door Trino maar via DuckDB. Die staan in Dagster, niet in dit log. Alleen afnemers gaan door de voordeur, en die worden vastgelegd.

## Overwogen

- **De OpenLineage-listener** naar OpenMetadata: geeft herkomst, maar geen volledig toegangslog met gebruiker en SQL. Kan er later náást (DF-ADR-007).
- **De Kafka-listener:** zwaar voor een PoC.
- **Een aparte dienst als ontvanger:** schoner, maar weer iets om te beheren. Het portaal heeft al een database met de juiste rechten en een zoekpagina.

## Aanvulling (27 november 2026)

Trino logt nu in via Keycloak (DF-ADR-017). De gebruiker in het log is daarmee een geverifieerd e-mailadres, of de dienst `openmetadata`.
