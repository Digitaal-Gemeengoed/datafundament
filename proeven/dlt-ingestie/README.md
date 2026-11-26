# Proef: ingestie met dlt naar Iceberg

dlt leest de bron op dfw (over WireGuard, als `dlt_lezer`) en schrijft naar Iceberg via Lakekeeper op Garage. De proef hergebruikt de opstelling van [`iceberg-schrijfpad`](../iceberg-schrijfpad/README.md).

## Wat de proef laat zien

1. **De weg naar de bron werkt:** WireGuard, het poortfilter, `pg_hba.conf` en de leesrechten. De bron meldt vanaf welk adres we binnenkomen (10.67.0.1).
2. **dlt schrijft Iceberg via de REST-catalogus**, met pyiceberg (dlt 1.32).
3. **Twee vormen van de ruwe laag:**
   - `ruw_brp`, insert-only: elke versie van een rij wordt toegevoegd. Er wordt nooit iets overschreven; dit is de volledige historie op ruw niveau (DF-ADR-005).
   - `ruw_brp_stand`, upsert op `id`: de huidige stand van de bron.
4. **Incrementeel laden:** na een verhuizing op dfw laadt dlt alleen de gewijzigde rijen, op basis van `gewijzigd_op`.
5. **Trino leest** wat dlt schreef.

## Waarom niet SCD2 en waarom nog niet logische replicatie

- dlt ondersteunt voor Iceberg de strategieën `upsert` en `insert-only`, niet `scd2`. De insert-only-laag geeft dezelfde historie, zonder iets te overschrijven. SCD2 met geldigheidsdatums maakt dbt in de uniforme laag.
- Deze proef laadt incrementeel op `gewijzigd_op`. Dat ziet wijzigingen, maar geen verwijderde rijen. Logische replicatie (`pg_replication`, DF-ADR-006) ziet ook die; dat is de volgende proef, als deze werkt.

## Draaien (op dfc)

```
cd /opt/datafundament/proeven/dlt-ingestie
sudo ./proef.sh
```

Het script vraagt één keer het wachtwoord van `dlt_lezer` (op dfw: `sudo ./bron.sh dlt-wachtwoord`). Halverwege vraagt het om op dfw een verhuizing te doen.
