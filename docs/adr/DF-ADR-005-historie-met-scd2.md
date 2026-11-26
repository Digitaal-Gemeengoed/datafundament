# DF-ADR-005 — Historie met SCD2, niet met time travel

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

Het voorstel belooft "volledige historie op zowel ruw als geüniformeerd niveau" en noemt daarvoor *time travel* van Iceberg. Maar een snapshot van Iceberg is technische historie: het laat zien hoe de tabel er na een schrijfactie uitzag. Snapshots moeten regelmatig worden opgeruimd, anders groeien opslag en metadata zonder grens. Na het opruimen is die historie weg.

Voor de vraag "wat wisten we op datum X over persoon of object Y" is functionele historie nodig, met geldigheid per rij. Dat is ook wat de Archiefwet en de uitlegbaarheid van een dataproduct vragen.

## Besluit

- **Ruwe laag:** dlt laadt met de strategie `scd2`. Elke versie van een rij krijgt een begin en einde van geldigheid (in dlt in te stellen als `geldig_vanaf` en `geldig_tot`).
- **Uniforme laag:** dbt-snapshots (SCD2) op de bedrijfssleutel.
- **Time travel:** alleen voor herstel en controle. Snapshots worden na een vaste termijn opgeruimd, in de PoC 30 dagen, door een job in Dagster.

## Gevolgen

- Historie is gewone data: op te vragen met SQL via Trino, en ook na het opruimen van snapshots aanwezig.
- Tabellen worden groter en vragen zonder datumfilter iets langzamer. Voor deze hoeveelheden is dat geen probleem.
- In de demo laten we beide zien: een SCD2-tijdlijn van een object, en een tabel die met time travel terug in de tijd wordt bekeken.

## Overwogen

- **Alleen time travel:** minder werk, maar het belooft meer dan het waarmaakt.
- **Snapshots nooit opruimen:** time travel als historie, maar de metadata groeit zonder grens, en de historie hangt af van één catalogus.
