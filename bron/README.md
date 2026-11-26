# De bron (dfw)

Een BRP-database met testpersonen, plus synthetische gemeentelijke bronnen eromheen, als bronsystemen voor de PoC (DF-ADR-010). Hij draait op dfw, apart van het lakehouse, en is alleen via WireGuard bereikbaar voor dfc (DF-ADR-009). dlt op dfc leest hem met logische replicatie (CDC, DF-ADR-006).

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

## Synthetische bronnen

Rond de BRP maakt `werkbank/synthetisch.py` zes bronnen, elk een eigen schema (DF-ADR-010). Alles is verzonnen, maar hangt samen: via BSN met de BRP en via de BAG met elkaar. Met de testdata van nu:

| Schema | Tabellen (rijen) |
|---|---|
| `bag` | woonplaats (107), openbare_ruimte (475), nummeraanduiding (842), pand (825), verblijfsobject (842) |
| `woz` | object (837), waarde (4.185), belanghebbende (1.310) |
| `belastingen` | aanslag (3.201) |
| `mor` | melding (3.000), status (8.935) |
| `zaken` | zaaktype (7), zaak (171), status (474) |
| `sociaal` | wmo_voorziening (42), jeugdhulp_traject (7), participatiewet_uitkering (17) |

Bewust ingebouwd, om in dbt te vinden: 11 BRP-adressen ontbreken in de BAG, 8 keer wijkt de postcode af, 5 bewoonde verblijfsobjecten zijn ingetrokken, 14 keer noemt de BRP een ongeldige of dubbele BAG-identificatie, en 61 woningen staan leeg.

De generator gebruikt een vaste seed en "vandaag" = 26 november 2026: opnieuw maken geeft dezelfde data.

Uniformeren (datums, codes, namen) gebeurt bewust niet hier, maar in het lakehouse met dbt. Daar laat de PoC zien hoe dat werkt.

Het schema in `sql/02-schema.sql` is gemaakt met `python werkbank/brp.py schema`; wijzig het niet met de hand.

## Bedienen (op dfw)

```
cd /opt/datafundament/bron
sudo ./bron.sh start          # eerste keer: maakt wachtwoorden en het schema
sudo ./bron.sh laden          # haalt de testdata op en laadt 666 personen
sudo ./bron.sh synthetisch    # de synthetische bronnen rond de BRP (opnieuw = dezelfde data)
sudo ./bron.sh status
```

Voor de demo van CDC en schemawijziging:

```
sudo ./bron.sh verhuis              # iemand verhuist; het oude adres wordt historie
sudo ./bron.sh verhuis 999997889    # een bepaalde persoon (Den Haag)
sudo ./bron.sh overlijden
sudo ./bron.sh kolom-erbij          # nieuwe kolom in brp.persoon
sudo ./bron.sh melding              # nieuwe melding openbare ruimte
sudo ./bron.sh zaak-afhandelen      # de oudste open zaak wordt afgehandeld
```

Elke mutatie is één transactie, zoals een BRP-systeem die zou doen. Via logische replicatie komt zij binnen enkele seconden bij dlt aan.

## Toegang

- `bron`: eigenaar, alleen vanuit de werkbank (compose-netwerk 172.30.67.0/24) en binnen de container.
- `dlt_lezer`: lezen en replicatie, alleen vanaf dfc (10.67.0.1). Het wachtwoord: `sudo ./bron.sh dlt-wachtwoord`.
- Publicatie `datafundament`: alle tabellen in `brp`, `bag`, `woz`, `belastingen`, `mor`, `zaken` en `sociaal`, ook tabellen die later bijkomen.
- Een replicatieslot dat niemand leest, houdt hoogstens 2 GB WAL vast (`max_slot_wal_keep_size`).
