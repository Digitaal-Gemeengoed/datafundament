# DF-ADR-020 — Toegang tot data voor een groep, en rechten in Lakekeeper uit het portaal

- **Status:** aanvaard
- **Datum:** 27 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

Rechten staan in het portaal, in groepen (DF-ADR-012, DF-ADR-013). Toegang tot een dataproduct ging per persoon: een aanvraag met doel en grondslag, beoordeeld door een ander (DF-ADR-017). Voor een team dat samen aan een opgave werkt, betekent dat een aanvraag per lid, en bij elke wisseling in het team een nieuwe.

Lakekeeper logt sinds DF-ADR-019 in via Keycloak en kent rechten in OpenFGA. Maar alleen de service-accounts en de eerste beheerder hadden daar rechten. Een collega met het recht 'Dagster en catalogus bedienen' kwam wel door de poort (DF-ADR-018), maar zag in de catalogus niets.

## Besluit

**Toegang voor een groep.**
- Een toegangsaanvraag kan voor een groep zijn in plaats van voor de aanvrager alleen. De aanvrager moet lid zijn.
- Doel, grondslag, einddatum en "met persoonsgegevens" werken zoals bij een aanvraag voor één persoon.
- Na toekenning geldt de toegang voor iedereen die op dat moment lid en actief is. Wie erbij komt, krijgt haar binnen een minuut in Trino; wie eruit gaat of geblokkeerd wordt, verliest haar.
- **Vier ogen:** wie lid is van de groep, beoordeelt de aanvraag niet. Het portaal weigert dat, en de database ook.
- De groep ligt vast bij de aanvraag; de naam wordt bewaard. Verdwijnt de groep, dan geldt de toekenning voor niemand meer. Een nieuwe groep met dezelfde naam krijgt haar niet.
- Bij de groepen staat welke data erbij hoort. Wie iemand aan een groep toevoegt, ziet dus wat die persoon daarmee krijgt.

**Rechten in Lakekeeper uit het portaal.**
- Elke 30 seconden zet het portaal in Lakekeeper, als service-account `df-lk-beheer`:
  - wie `platform.bedienen` heeft, krijgt `describe` op het project: warehouses, namespaces, tabellen, schema's en snapshots zien. Geen data: die staat in Garage, en Lakekeeper geeft geen sleutels (DF-ADR-018);
  - wie superadmin is, krijgt `project_admin`.
- Wie het recht verliest, of geblokkeerd of gedeactiveerd wordt, verliest het ook in Lakekeeper.
- Het portaal houdt bij wat het zelf gaf (tabel `lakekeeper_toewijzingen`) en trekt alleen dat in. Wat het installatiescript zette (de eerste beheerder, de service-accounts), blijft.
- Een mens heet in Lakekeeper `oidc~<id in Keycloak>`. Het portaal neemt dat id uit de eerste inlog, of zoekt het op in Keycloak. Het meldt de gebruiker in Lakekeeper aan voordat het rechten geeft.

## Gevolgen

- Een team vraagt één keer aan. Het lidmaatschap van een groep is daarmee ook een recht op data. Lidmaatschappen veranderen kan alleen met `accounts.manage` of `groups.manage`, en staat in de audit.
- **Niemand zet zichzelf in een groep met toegang:** je eigen groepen wijzig je niet zelf (al zo in het portaal). Wel kan een accountbeheerder een collega toevoegen. De vier ogen gelden bij de aanvraag, niet bij het lidmaatschap. Geef `accounts.manage` daarom aan andere mensen dan `toegang.beoordelen`. Elke wijziging van een lidmaatschap staat in de audit.
- Lakekeeper volgt het portaal binnen een minuut; Lakekeeper is daarvoor geen tweede plek om rechten te beheren. Wie in Lakekeeper met de hand een recht geeft, houdt dat: het portaal komt er niet aan.
- `describe` toont ook de metadata van een tabel, met de paden van de bestanden in Garage. Dat is geen data, en Garage is van buiten niet bereikbaar.

## Getest

- Toegang voor een groep: alleen voor de eigen groep aanvragen, geen beoordeling door een lid (portaal en database), toegang voor alle actieve leden, toegang volgt het lidmaatschap en de status, geen toegang meer na het verwijderen van de groep (`backend/test/groepen-en-catalogus.test.ts`).
- Lakekeeper:
  - met een nagebootste Lakekeeper: geven, niets vragen als er niets veranderde, en alleen intrekken wat het portaal gaf;
  - lokaal tegen Lakekeeper 0.13.9 met OpenFGA en Keycloak: een gebruiker zonder recht ziet niets. Met `describe` ziet hij warehouse, namespaces en tabellen, maar mag hij geen namespace maken. Na intrekken ziet hij weer niets.

## Overwogen

- **Een groep in Keycloak voor Lakekeeper:** dan staan de rechten op twee plekken (DF-ADR-012).
- **Toegang per groep zonder vier-ogenregel voor leden:** dan kent een beoordelaar in de groep zichzelf toegang toe.
- **Lakekeeper-rechten per namespace of tabel uit het portaal:** nu niet nodig, want data lezen loopt via Trino. Kan later met dezelfde koppeling.
