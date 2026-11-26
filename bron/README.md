# De bron (dfw)

Een BRP-database met testpersonen, plus synthetische inwoners en gemeentelijke bronnen eromheen, als bronsystemen voor de PoC (DF-ADR-010). Hij draait op dfw, apart van het lakehouse, en is alleen via WireGuard bereikbaar voor dfc (DF-ADR-009). dlt op dfc leest hem met logische replicatie (CDC, DF-ADR-006).

## Wat erin zit

De testpersonen uit vrijBRP (Procura, EUPL-1.2), module `gba-testdata` van [vrijBRP-Balie](https://github.com/vrijBRP/vrijBRP-Balie), vastgepind op commit `fb9f41b`:

| Testset | Persoonslijsten | Herkomst |
|---|---|---|
| `gbav` | 665 | testset GBA-V |
| `rvig` | 437 | testpersonen van de RvIG |
| `demo` | 21 | demopersonen van Procura |

De sets overlappen; na ontdubbelen op A-nummer zijn het **666 personen**. In `brp.persoonslijst.testsets` staat in welke set(s) iemand voorkomt.

Het zijn fictieve personen, ook in fictieve testgemeenten van de RvIG (zoals Drogezand en Gansdorp). De meeste wonen volgens de testdata in Stichtse Vecht, Den Haag, Rotterdam en Amsterdam.

## Het schema

Zoals een BRP-systeem het opslaat: per categorie van het LO BRP een tabel, per rubriek een kolom, met historie.

- `brp.persoonslijst`: één rij per persoon (A-nummer, BSN, testsets).
- `brp.persoon`, `brp.ouder_1`, `brp.ouder_2`, `brp.nationaliteit`, `brp.huwelijk`, `brp.overlijden`, `brp.inschrijving`, `brp.verblijfplaats`, `brp.kind`, `brp.verblijfstitel`, `brp.gezag`, `brp.reisdocument`, `brp.kiesrecht`, `brp.woningkaart`.
  - Elke rij: `stapel`, `volgnr`, `actueel` (de actuele stand; de andere rijen zijn historie), `onjuist`, `gewijzigd_op`.
  - Elke rubriek als tekst, zoals de bron hem levert: datums als `JJJJMMDD`, codes als code. Het commentaar bij elke kolom noemt de rubriek, bijvoorbeeld `08.11.60 postcode`.
- `brp.codetabel`: codes met hun omschrijving, zoals de testdata ze levert (gemeenten, landen, nationaliteiten, redenen).

## Synthetische inwoners en bronnen

`werkbank/inwoners.py` zet ongeveer 1.500 synthetische huishoudens (ruim 3.000 personen) in de BRP, op huisnummers rond de adressen van de testpersonen. `werkbank/synthetisch.py` maakt daaromheen zes bronnen, elk een eigen schema (DF-ADR-010, DF-ADR-014). Alles is verzonnen, maar hangt samen: via BSN met de BRP en via de BAG met elkaar.

| Schema | Tabellen | dfc krijgt het via |
|---|---|---|
| `bag` | woonplaats, openbare_ruimte, nummeraanduiding, pand, verblijfsobject | de database (CDC-light) |
| `woz` | object, waarde, belanghebbende (met begin- en einddatum) | de database |
| `mor` | melding, status | de database |
| `sociaal` | wmo_voorziening, jeugdhulp_traject, participatiewet_uitkering | de database |
| `zaken` | zaaktype, zaak, status | de **Zaken-API** op poort 8000 |
| `belastingen` | aanslag | een **nachtelijke export** naar de bucket `landing` op dfc |

Bewust ingebouwd, om in dbt te vinden: BRP-adressen die in de BAG ontbreken, een afwijkende postcode, bewoonde verblijfsobjecten die zijn ingetrokken, ongeldige BAG-identificaties in de BRP, en leegstand. De generator meldt hoeveel.

## De simulatieklok

Vanaf 27 november 2026 leeft de gemeente door, uur na uur, een jaar lang (`werkbank/simulatie.py`):

- **BRP:** geboorte, overlijden, verhuizing, vestiging en vertrek, alleen bij synthetische inwoners;
- **BAG:** bouwprojecten;
- **WOZ:** waarden op 1 januari;
- **belastingen:** aanslagen eind februari, betalingen en aanmaningen;
- **meldingen:** met een seizoen;
- **zaken:** statusverloop in kantoortijd;
- **sociaal domein:** voorzieningen die beginnen en eindigen.

Elk uur heeft een eigen seed, dus opnieuw draaien geeft hetzelfde jaar. Er wordt nooit iets verwijderd. Lokaal gedraaid (een jaar in anderhalve minuut) gaf dat ongeveer 1.650 meldingen, 310 verhuizingen, 30 geboorten, 12 bouwprojecten en 620 zaken.

`sim.voortgang` zegt tot waar de klok is; `sim.logboek` wat er gebeurde. Het schema `sim` is niet voor dfc.

## De Zaken-API

`werkbank/zaken_api.py`, naar het voorbeeld van de Zaken- en Catalogi-API van VNG, alleen lezen:

- **Endpoints:** `/catalogi/api/v1/zaaktypen`, `/zaken/api/v1/zaken`, `statussen`, `rollen` (de initiator, met BSN of NNP) en `zaakobjecten` (het BAG-object).
- **Inloggen:** een JWT (HS256) met `client_id`, zoals bij ZGW.
- **Pagina's** van 100.
- **Eén uitbreiding:** `?gewijzigd__gt=` en het veld `gewijzigdOp`. De standaard kent geen filter op wijzigingen.

Proberen vanaf dfc:

```
TOKEN=$(sudo docker compose -f /opt/datafundament/compose/compose.yml exec -T werk \
  python -c "import os; from ingestie.zaken_api import token; print(token(os.environ['ZAKEN_API_GEHEIM']))")
curl -s -H "Authorization: Bearer $TOKEN" http://10.67.0.2:8000/zaken/api/v1/zaken | head -c 600
```

## De nachtelijke export

`werkbank/export.py` zet elke nacht om 02:15 de aanslagen die sinds de vorige export zijn gewijzigd in `landing/belastingen/aanslag/`. De eerste keer gaat alles mee. Het formaat is dat van een doorsnee leverancier:

- CSV met puntkomma's;
- bedragen met een komma;
- datums als dd-mm-jjjj;
- kopjes in gewone taal.

De sleutel mag alleen schrijven in de bucket `landing`.

Uniformeren (datums, codes, namen) gebeurt bewust niet hier, maar in het lakehouse met dbt. Daar laat de PoC zien hoe dat werkt.

Het schema in `sql/02-schema.sql` is gemaakt met `python werkbank/brp.py schema`; wijzig het niet met de hand.

## Bedienen (op dfw)

```
cd /opt/datafundament/bron
sudo ./bron.sh start              # eerste keer, en na elke git pull: wachtwoorden, database, Zaken-API
sudo ./bron.sh laden              # haalt de testdata op en laadt 666 personen
sudo ./bron.sh synthetisch        # synthetische inwoners en bronnen; zet de klok op 27 november 2026
sudo ./bron.sh status
```

`synthetisch` alleen bij de start draaien. Opnieuw draaien verwijdert de synthetische personen, en die verwijdering ziet de ingestie niet.

De simulatie en de export aanzetten:

```
sudo ./bron.sh zaken-api-geheim   # voor dfc (installeer-platform.sh vraagt erom)
sudo ./bron.sh landing-sleutel    # de sleutel die installeer-platform.sh op dfc toont
sudo ./bron.sh export-belastingen # één keer met de hand: de volledige export
sudo ./bron.sh simulatie-aan      # klok elk uur, export elke nacht
sudo ./bron.sh simulatie-status
```

Voor een demo met de hand:

```
sudo ./bron.sh verhuis              # iemand verhuist; het oude adres wordt historie
sudo ./bron.sh verhuis 999997889    # een bepaalde persoon (Den Haag)
sudo ./bron.sh overlijden
sudo ./bron.sh kolom-erbij          # nieuwe kolom in brp.persoon
sudo ./bron.sh melding              # nieuwe melding openbare ruimte
sudo ./bron.sh zaak-afhandelen      # de oudste open zaak wordt afgehandeld (zichtbaar via de API)
```

Elke mutatie is één transactie, zoals een BRP-systeem die zou doen.

## Toegang

- `bron`: eigenaar, alleen vanuit de werkbank (compose-netwerk 172.30.67.0/24) en binnen de container.
- `dlt_lezer`: lezen en replicatie, alleen vanaf dfc (10.67.0.1). Het wachtwoord: `sudo ./bron.sh dlt-wachtwoord`.
- `zaken_api`: alleen lezen in het schema `zaken`, alleen vanuit het compose-netwerk (de Zaken-API).
- De Zaken-API (poort 8000) is alleen bereikbaar voor dfc (10.67.0.1), met een JWT.
- Publicatie `datafundament`: alle tabellen in `brp`, `bag`, `woz`, `mor` en `sociaal`, ook tabellen die later bijkomen. Niet `zaken` en `belastingen`: die komen via de API en de export.
- Een replicatieslot dat niemand leest, houdt hoogstens 2 GB WAL vast (`max_slot_wal_keep_size`).
