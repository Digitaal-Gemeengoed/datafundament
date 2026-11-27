# DF-ADR-006 — CDC in de PoC alleen op een Postgres-bron

- **Status:** aanvaard (uitgevoerd 27 november 2026)
- **Datum:** 26 november 2026
- **Besloten door:** Erik Hoekstra

## Context

Het voorstel noemt "geautomatiseerde ontsluiting van bronnen inclusief CDC". dlt kan incrementeel laden (op een kolom met een tijdstip of volgnummer) en de logische replicatie van PostgreSQL lezen.

Echte CDC op de bronnen van een gemeente is een ander verhaal. Veel bronnen zijn Oracle of SQL Server achter een leverancierspakket. Daar is CDC vaak afgeschermd, het vraagt medewerking van de leverancier, of er zijn extra licenties voor nodig.

## Besluit

- **De PoC toont CDC op één PostgreSQL-bron**, via logische replicatie met dlt (`pg_replication`). Bij voorkeur is dat de database met testdata van VrijBRP (DF-ADR-010).
- **Andere bronnen** laden incrementeel of volledig.
- In de demo en in de documentatie zeggen we dat zo: CDC is bewezen voor PostgreSQL. Voor andere databases is het per bron een eigen vraagstuk.

## Gevolgen

- Een eerlijke claim die een beheerder of leverancier niet onderuit kan halen.
- De replicatie vraagt `wal_level=logical` en een replicatiegebruiker op de bron. Dat zetten we in de compose van de bron.
- Voor een vervolg is een inventarisatie per bron nodig: database, toegang, mogelijkheden voor CDC.

## Overwogen

- **Debezium met Kafka:** CDC voor veel databases, maar te zwaar voor een PoC en tegen de lichte opzet van DF-ADR-001. Dit sluit aan bij OA-ADR-003, waar om dezelfde reden voor een outbox is gekozen.

## Stand (26 november 2026)

- **Bewezen:** dlt leest de bron op dfw over WireGuard als `dlt_lezer` (de bron ziet 10.67.0.1) en laadt incrementeel op `gewijzigd_op`. Na een verhuizing komen alleen de twee gewijzigde rijen en de persoonslijst binnen.
- **Grens van die aanpak:** verwijderde rijen ziet hij niet, en na een grote lading delen veel rijen hetzelfde tijdstip (dlt waarschuwt daarvoor; het werkt wel).
- **Nog te doen:** logische replicatie (`pg_replication`), die ook verwijderingen ziet. De publicatie `datafundament` staat al klaar op de bron. Tot dat werkt, is incrementeel laden de terugval.

## Aanvulling (26 november 2026)

Naast CDC-light op PostgreSQL zijn er nu ook een API (zaken) en een nachtelijk bestand (belastingen) als ingestiepatroon; zie DF-ADR-014.

## Uitgevoerd (27 november 2026): echte CDC

De databasebronnen (`brp`, `bag`, `woz`, `mor`, `sociaal`) komen nu binnen via de logische replicatie van PostgreSQL. Niet met de `pg_replication`-bron van dlt, maar met een eigen lezer van ongeveer 200 regels (`ingestie/cdc.py`). Die is kleiner dan het geheel van dlt, en zo blijft de pseudonimisering op één plek.

- **Publicaties met kolomlijsten.** Per bron één publicatie, `df_<bron>`, die per tabel de kolommen noemt. Namen en A-nummers staan er niet in, dus die gaan nooit over de lijn, net als bij het incrementeel lezen (DF-ADR-015). Een nieuwe kolom komt pas door als de publicatie is bijgewerkt (`bron.sh publicaties`). Dat is bewust: een nieuwe kolom met persoonsgegevens glipt er niet vanzelf in.
- **Een slot per laag.** `df_ruw_<bron>` en `df_ruw_<bron>_stand` lezen elk alle wijzigingen, los van elkaar. De Dagster-assets blijven hetzelfde.
- **Kijken, schrijven, dan opschuiven.** dfc leest met `pg_logical_slot_peek_binary_changes`, in porties van hele transacties. Het decodeert pgoutput, schrijft met dlt naar Iceberg en schuift het slot pas daarna op (`pg_replication_slot_advance`). Gaat er iets mis, dan komt de portie opnieuw: at-least-once. Een open replicatieverbinding is niet nodig, dus er is ook geen time-out tijdens het schrijven.
- **De eerste keer** maakt dfc het slot aan en laadt nog één keer incrementeel op `gewijzigd_op`. Wat daartussen wijzigt, komt nog een keer via het slot. Hetzelfde gebeurt na een vervallen slot (te ver achter, boven 2 GB WAL) en na `beheer.opnieuw_laden`, dat de slots weggooit.
- **Verwijderingen.**
  - In `ruw_<bron>` komt een rij met alleen het id en `_cdc_bewerking = 'D'`. Daarom mogen in de ruwe lagen alle kolommen behalve de sleutel leeg zijn.
  - In `ruw_<bron>_stand` gaat de rij eruit, met een Iceberg-delete; de upsert van dlt op Iceberg kent geen hard delete.
  - De tijdlijn in `uniform.verblijfplaats_historie` sluit af op het moment van de verwijdering.
- **Nieuwe kolommen** in de ruwe lagen:
  - `_cdc_bewerking` (I, U, D), alleen in `ruw_<bron>`;
  - `_cdc_lsn` en `_cdc_tijdstip` (de commit), in beide lagen.
- **Een aanvulling op pyiceberg 0.12** (`ingestie/iceberg_upsert.py`): na een nieuwe kolom faalde de upsert. Dat gold ook al voor de schemawijziging uit de demo.

**Grenzen.**
- TRUNCATE wordt niet gepubliceerd. Na het opnieuw vullen van een bron hoort `beheer.opnieuw_laden`.
- Een ongewijzigde TOAST-waarde (groter dan ongeveer 2 kB, niet gewijzigd bij een UPDATE) komt niet mee. In deze bronnen komt dat niet voor; Dagster waarschuwt als het toch gebeurt.
- `CDC=uit` in de omgeving zet terug naar incrementeel laden.

**Getest** met PostgreSQL 16 (`ingestie/test_cdc.py`):
- inhaalslag;
- update, verwijdering en twee updates achter elkaar;
- pseudoniemen gelijk aan die van de inhaalslag;
- geen namen in de berichten van het slot;
- de afgesloten tijdlijn;
- een nieuwe kolom vóór en na het bijwerken van de publicatie.
