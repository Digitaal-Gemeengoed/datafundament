# DF-ADR-014 — Een gesimuleerd jaar, en drie manieren waarop data binnenkomt

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

Met vaste testdata laat de PoC één wijziging zien. Een datafundament moet laten zien hoe het zich gedraagt als de bronnen elke dag veranderen: historie die groeit, dataproducten die met de tijd meebewegen, en een keten die blijft draaien.

Daarnaast deed de PoC alsof alle data rechtstreeks uit een database komt (CDC). Bij een gemeente is dat zelden zo. Een leverancier biedt een API, of levert elke nacht een bestand. DF-ADR-006 noemde dat al als beperking.

## Besluit

**1. Synthetische inwoners.** Naast de 666 testpersonen van vrijBRP komen ongeveer 1.500 huishoudens (ruim 3.000 personen) in de BRP:

- met ouders, kinderen en huwelijken over en weer;
- op huisnummers rond de adressen van de testpersonen, in dezelfde postcode, zodat de BAG en de buurten kloppen;
- met een BSN dat aan de elfproef voldoet, in een eigen reeks, en testset `synthetisch`.

De testpersonen zelf blijven ongemoeid, want het zijn testgevallen.

**2. Een simulatieklok** (`bron/werkbank/simulatie.py`). Vanaf 27 november 2026 maakt de klok elk uur de mutaties van dat uur, een jaar lang:

- **BRP:** geboorte, overlijden, verhuizing, vestiging van buiten, vertrek naar het buitenland;
- **BAG:** bouwprojecten van vergunning tot ingemeten;
- **WOZ:** nieuwe waarden op 1 januari; eigenaar en gebruiker volgen de BRP;
- **belastingen:** aanslagen eind februari, betalingen, aanmaningen en kwijtschelding;
- **meldingen:** met een seizoen (blad, gladheid, vuurwerk);
- **zaken:** statusverloop binnen kantoortijd;
- **sociaal domein:** voorzieningen die beginnen en eindigen.

Hoe de klok werkt:

- Elk uur heeft een eigen seed. Dezelfde begintoestand geeft dus hetzelfde jaar, en opnieuw draaien geeft dezelfde data.
- Een systemd-timer op dfw draait de klok elk uur en haalt gemiste uren in.
- Er wordt nooit iets verwijderd. Een einde is een einddatum of een nieuwe status, zoals in een echte registratie.

**3. Drie ingestiepatronen**, zoals bij een echte gemeente:

| Patroon | Bronnen | Hoe |
|---|---|---|
| Database (CDC-light, DF-ADR-006) | brp, bag, woz, mor, sociaal | dlt leest PostgreSQL incrementeel op `gewijzigd_op` |
| API | zaken | Zaken-API naar het voorbeeld van ZGW (Zaken- en Catalogi-API), met JWT en paginering; dlt leest met zijn REST-bron |
| Bestand | belastingen | elke nacht een CSV-export in de bucket `landing` in Garage; dlt leest alleen de nieuwe bestanden |

- Zaken en belastingen zijn niet meer rechtstreeks uit de database te lezen: `dlt_lezer` heeft er geen rechten meer op en ze staan niet in de publicatie.
- De Zaken-API heeft één uitbreiding op de standaard: het filter `gewijzigd__gt` en het veld `gewijzigdOp`. De ZGW-API's kennen geen filter op wijzigingen.
- Het exportbestand heeft de eigenaardigheden van een doorsnee leverancier: puntkomma's, een komma in bedragen, datums als dd-mm-jjjj en kopjes in gewone taal. Uniformeren gebeurt in dbt.
- De leverancier op dfw heeft een sleutel die alleen mag schrijven in de bucket `landing`. Garage is daarvoor via WireGuard bereikbaar voor dfw, en alleen op poort 3900.

**4. Onderhoud.** Elke nacht ruimt een job in Dagster de snapshots op die ouder zijn dan een week, in alle Iceberg-tabellen.

## Gevolgen

- De PoC laat na een paar weken trends zien: verhuizingen, meldingen per seizoen, doorlooptijden en betaalgedrag. Die trends zijn wel gemaakt. Wat je erin vindt, zit er door de simulatie in; het zegt niets over een echte gemeente.
- Het verschil tussen de drie patronen wordt zichtbaar, met de problemen die erbij horen:
  - **API:** zonder filter op wijzigingen moet je alles opnieuw ophalen, of de Notificaties-API gebruiken. Deze PoC voegt dat filter zelf toe; een echte ZGW-API heeft het niet.
  - **Bestand:** een regel kan twee keer komen (minstens één keer, door een marge van tien minuten), en alles komt binnen als tekst.
  - **Database:** verwijderde rijen ziet de ingestie niet.
- **Kleine bestanden.** Een ingestie om de vijf minuten maakt veel kleine bestanden en snapshots. Snapshots ruimen we op. Kleine bestanden samenvoegen en bestanden zonder snapshot opruimen kan pyiceberg nog niet. Daarvoor is een schrijvende engine nodig, zoals Spark of Trino met een eigen onderhoudscatalogus. Dat is een vervolgstap.
- **Alleen voor de start.** Opnieuw `synthetisch` draaien verwijdert de synthetische personen en zet de klok terug. Doe dat alleen bij de start: de ruwe laag houdt de oude rijen, omdat CDC-light geen verwijderingen ziet.

## Overwogen

- **Open Zaak draaien in plaats van een eigen API.** Dat is het meest echt, maar zwaar voor de VPS 6 van dfw en veel werk. Het blijft een optie voor later.
- **Een SFTP-server voor de export.** Dat is herkenbaar, maar het is een extra dienst. Een bucket met een sleutel die alleen mag schrijven doet hetzelfde, met wat er al is.
- **Alleen de 666 testpersonen laten muteren.** Dan gebeurt er te weinig, en verliezen de testgevallen hun betekenis.
