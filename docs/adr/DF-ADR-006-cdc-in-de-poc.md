# DF-ADR-006 — CDC in de PoC alleen op een Postgres-bron

- **Status:** aanvaard
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
