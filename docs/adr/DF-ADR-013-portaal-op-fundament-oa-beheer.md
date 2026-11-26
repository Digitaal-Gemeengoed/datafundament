# DF-ADR-013 — Een portaal op het fundament van oa-beheer

- **Status:** voorgesteld
- **Datum:** 26 november 2026
- **Voorgesteld door:** Claude, op vraag van Erik Hoekstra

## Context

De stack heeft geen gemeenschappelijke ingang voor data-engineers en platformbeheerders. Elk onderdeel heeft een eigen scherm: Dagster, OpenMetadata, Lakekeeper, de web-UI van Trino. Wat ontbreekt:

- één plek om te beginnen, met één keer inloggen;
- een overzicht van dataproducten en hun stand, over de onderdelen heen;
- een plek om toegang tot een dataproduct aan te vragen en te verlenen;
- voor platformbeheer: de gezondheid van de onderdelen, wie welke rol heeft, en het log van vragen in Trino.

Het beheerportaal van de Office Assistent (`oa-beheer`) heeft een fundament dat precies het moeilijke deel al doet:

- inloggen via Keycloak met PKCE, nonce en tweede factor;
- sessies, een noodaccount en een audit met hashketen;
- beveiligingskoppen, en invoercontrole met JSON Schema;
- NL Design System, opgezet volgens OWASP ASVS niveau 2.

Daar komen de pagina's voor het eigen domein bovenop.

## Voorstel

1. **Het fundament van `oa-beheer` overnemen**, met de herkomst (repo en commit) in de README:
   - **wel:** inloggen, sessies, noodaccount, audit, instellingen, profiel, accounts en groepen, de huisstijl;
   - **niet:** wat bij de Office Assistent hoort (gemeenten, medewerkers, classificatie, metadatamodel, anonimiseren).
2. **Het portaal regelt geen toegang tot data.** Rechten op data blijven in Trino en Lakekeeper (DF-ADR-008). Het portaal toont ze, en zet een goedgekeurde aanvraag om in een wijziging van die regels, als commit of pull request in Git. Er komt dus geen tweede plek waar rechten op data staan.
3. **Het portaal vervangt geen schermen die er al zijn.** Het linkt naar Dagster, OpenMetadata, Lakekeeper en Trino, en toont alleen wat over de onderdelen heen gaat.
4. **Eerste pagina's:**
   - *Start*: de onderdelen met hun stand en een link;
   - *Dataproducten*: uit OpenMetadata en Dagster, met eigenaar, laatste run en kwaliteit;
   - *Toegang*: aanvragen en beoordelen;
   - *Platform*: gezondheid, rollen, en het log van Trino.
5. **Later:** het fundament wordt een gedeeld pakket of sjabloon voor beide portalen, zodat een beveiligingsfix maar één keer gebouwd hoeft te worden.
6. **Niet in de eerste week.** Dan volstaat een eenvoudige startpagina in Caddy met links.

## Gevolgen

- Een beproefd fundament in plaats van een nieuwe inlog en audit; Digitaal Gemeengoed onderhoudt één manier van bouwen.
- Het portaal is TypeScript en React, terwijl de rest van de stack Python en SQL is. Voor data-engineers is het dus een tweede taal. Dat is aanvaardbaar zolang het portaal dun blijft.
- Overnemen zonder gedeeld pakket betekent dat een fix in `oa-beheer` ook hier moet. Dat is een tijdelijke schuld, tot punt 5.
- Het portaal is maatwerk, en het voorstel wil maatwerk juist beperken. Daarom blijft het een ingang en een regiepunt, geen beheerlaag over de onderdelen heen.

## Overwogen

- **Geen portaal, alleen de schermen van de onderdelen:** geen maatwerk, maar ook geen overzicht en geen aanvraagstroom. En inloggen per onderdeel.
- **Een kant-en-klaar ontwikkelaarsportaal (Backstage):** krachtig, maar zwaar, en een eigen pluginmodel in een derde taal.
- **De catalogus van OpenMetadata als portaal:** goed voor dataproducten, niet voor platformbeheer en de toegangsstroom.
