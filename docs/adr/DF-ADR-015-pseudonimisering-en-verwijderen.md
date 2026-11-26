# DF-ADR-015 — Pseudoniemen bij de poort, een sleutelkluis, en verwijderen met crypto-shredding

- **Status:** aanvaard
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

De ruwe laag is insert-only en vergeet dus nooit iets (DF-ADR-005). Dat is sterk voor controle en voor de Archiefwet, maar het botst met de AVG:

- er is een recht op verwijdering (art. 17);
- er zijn bewaartermijnen, bijvoorbeeld voor jeugdhulp;
- en sommige gegevens zijn onrechtmatig verwerkt en moeten weg.

Daarbij stond het BSN, samen met namen, in alle lagen. Elke kopie van de data was dus een kopie van persoonsgegevens.

Twee dingen maken echt verwijderen in deze stack lastig:

- DuckDB en Trino kunnen geen gegevens ontsleutelen. Versleutelde kolommen in het lakehouse zijn dus onbruikbaar.
- Een `DELETE` in Iceberg schrijft alleen een markering. De oude Parquet-bestanden blijven staan tot herschrijven (compaction), het opruimen van snapshots en het opruimen van verweesde bestanden. Compaction kan nog niet (DF-ADR-014).

## Besluit

**1. Pseudoniemen bij de poort.**

- Bij de ingestie gaat het BSN er in elke bron uit. In de plaats komt een **pseudoniem**: een willekeurige UUID per persoon. Het pseudoniem is niet van het BSN afgeleid, dus ook met de sleutel van de kluis is het niet uit te rekenen.
- Namen en A-nummers (direct identificerend) worden niet eens gelezen.
- Het BSN wordt gelezen onder de naam van het pseudoniem en vervangen voordat er iets wordt weggeschreven. Er staat dus nooit een kolom met een BSN in het schema van dlt.
- Dit geldt voor alle drie de ingestiepatronen:
  - **database:** brp, woz, mor, sociaal;
  - **API:** zaken, het BSN zit genest in de rol;
  - **bestand:** belastingen.
- Hetzelfde BSN geeft in alle bronnen hetzelfde pseudoniem. Bronnen zijn dus nog steeds aan elkaar te koppelen.

**2. Een sleutelkluis.**

- Een eigen database `kluis` op dfc, met een eigen rol, niet via Trino te lezen.
- Daarin `kluis.koppeling (bsn_hmac, pseudoniem, vernietigd, verzoek)` en `kluis.blokkade (bron, sleutel)`.
- Het BSN staat ook hier niet in, alleen als HMAC-SHA256 met `KLUIS_GEHEIM`. Die sleutel delen de ingestie en het portaal.

**3. Verwijderen via het portaal, met vier ogen** (DF-ADR-013):

1. Iemand met `verwijderen.aanvragen` legt een verzoek vast met BSN, grondslag en reden. Het portaal bewaart alleen de HMAC en de laatste drie cijfers.
2. Een ander met `verwijderen.beoordelen` keurt het goed. Het portaal start dan de job `verwijderen` in Dagster, met alleen de HMAC.
3. De job:
   - zoekt het pseudoniem;
   - verwijdert de persoonslijst(en) uit `ruw_brp`, `ruw_brp_stand` en de uniforme laag, en de persoonsgebonden rijen uit het sociaal domein;
   - ruimt in die tabellen alle oude snapshots op;
   - zet de pl_id's op de blokkadelijst;
   - zet het pseudoniem in de kluis op NULL (**crypto-shredding**).
4. Het bewijs (aantallen per tabel, opgeruimde snapshots, tijdstip) komt via de log van Dagster terug in het portaal en in de audit. Het pseudoniem zelf komt nergens in een log: via het verzoek en de HMAC zou het dan weer te herleiden zijn.
5. Daarna krijgt dat BSN bij de ingestie geen nieuw pseudoniem:
   - persoonsgebonden rijen worden overgeslagen;
   - andere rijen krijgen een leeg pseudoniem;
   - BRP-rijen van de geblokkeerde pl_id's komen niet meer binnen.

**4. Eén keer opnieuw laden.** De ruwe lagen en de uniforme laag van vóór dit besluit bevatten BSN's en namen. `python -m beheer.opnieuw_laden --ja` gooit ze weg (met purge in Lakekeeper) en wist de staat van dlt. De volgende ingestie laadt alles opnieuw, gepseudonimiseerd.

## Gevolgen

- Het lakehouse bevat geen direct identificerende gegevens meer. Een gelekte kopie van Iceberg-bestanden bevat geen BSN of naam.
- Na een verwijdering wijzen pseudoniemen in WOZ, meldingen, zaken en belastingen nergens meer naar. Die gegevens over objecten blijven bruikbaar.
- **Eerlijk over de grenzen:**
  - **Indirect identificerend** zijn nog: geboortedatum, adres en de technische pl_id van de bron. Met de bron ernaast blijft een persoon te vinden. Pseudonieme gegevens zijn volgens de AVG nog steeds persoonsgegevens. Dataproducten moeten daarom aggregeren of generaliseren, en toegang loopt via Trino (DF-ADR-008).
  - **Fysiek:** na een verwijdering staan de oude Parquet-bestanden nog in Garage, tot compaction en het opruimen van verweesde bestanden er zijn (DF-ADR-014). Wie bij de opslag kan, kan ze nog lezen. Tot dan is "verwijderd" logisch: de rijen zijn weg uit elke tabel en elke snapshot.
  - **De bron** zelf (de BRP op dfw) verwijdert niets. Dat is aan de bronhouder. De blokkade voorkomt dat de persoon terugkomt.
- `ruw_brp` is niet meer strikt insert-only: een goedgekeurd verwijderverzoek is de enige uitzondering, met bewijs in de audit.
- **De kluis is een kroonjuweel.** Wie kluis én bron heeft, kan pseudoniemen herleiden. Daarom staat de kluis apart, niet in Trino, en heeft het portaal er geen toegang toe.

## Overwogen

- **Versleutelen per persoon in het lakehouse** (een sleutel per BSN, bijvoorbeeld in OpenBao zoals bij de Office Assistent): echte crypto-shredding van de waarden zelf. Maar DuckDB en Trino kunnen niet ontsleutelen, dus de data is in de lagen onbruikbaar. Voor later, als er een engine met ontsleuteling of een proxy bij komt.
- **Een HMAC als pseudoniem:** geen kluis nodig. Maar wie de sleutel heeft, kan het pseudoniem uit elk BSN opnieuw berekenen. Dan is er niets te shredden.
- **Alleen fysiek verwijderen:** sterkst, maar dat kan pas met een schrijvende engine voor compaction. Dat blijft de vervolgstap.
- **De kluis in OpenBao:** sterker beheer van de sleutel, maar een extra dienst die na elke herstart ontzegeld moet worden. Voor de PoC volstaat PostgreSQL met een eigen rol.
