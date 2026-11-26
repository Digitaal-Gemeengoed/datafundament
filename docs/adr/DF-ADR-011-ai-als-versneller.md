# DF-ADR-011 — AI als versneller; het resultaat is gewone, leesbare code

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Fabien (voorstel), Erik Hoekstra

## Context

De PoC wordt gebouwd met hulp van AI (*vibe coding*) om snel te kunnen laten zien wat werkt. Voor de besluitvorming moet duidelijk zijn dat het platform zelf niet van AI afhangt. Over niet-uitlegbare of niet-soevereine AI-oplossingen wordt in dit traject geen besluit gevraagd.

## Besluit

- **AI helpt alleen bij het bouwen.** In de werking en het beheer van het platform zit geen AI.
- **Het resultaat is gewone code**, die een data-engineer zonder AI kan lezen, wijzigen en beheren:
  - elk onderdeel in zijn eigen, gangbare vorm: SQL voor dbt, Python voor dlt en Dagster, `.properties` en JSON voor Trino, YAML voor OpenMetadata;
  - geen zelfgebouwde abstractielagen of generatoren rond die onderdelen;
  - een README per map: wat het doet en hoe je het draait;
  - tests waar het kan: dbt-tests voor data, pytest voor Python.
- **Elk besluit als ADR** in `docs/adr/`.
- **Herkomst:** commits die met AI zijn gemaakt, staan zo in Git (*Co-Authored-By*). Een mens beoordeelt en voegt samen.

## Gevolgen

- Wie de PoC overneemt, erft geen afhankelijkheid van een AI-dienst.
- Het tempo ligt iets lager dan "alles genereren", omdat code eenvoudig moet blijven en gecontroleerd wordt.

## Overwogen

- **AI ook in de keten**, bijvoorbeeld voor het herkennen van schema's of het voorstellen van kwaliteitsregels: bewust buiten de PoC gehouden, zodat het besluit over de architectuur zuiver blijft.
