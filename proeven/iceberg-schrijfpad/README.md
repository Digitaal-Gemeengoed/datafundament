# Proef: het schrijfpad naar Iceberg (DF-ADR-004)

Werkt de kern van de stack samen? DuckDB schrijft naar Iceberg via Lakekeeper, op Garage; Trino leest hetzelfde terug. Dit is het grootste technische risico van de PoC, daarom testen we het eerst, los van de rest.

## Wat de proef doet

1. Start Garage (één node), Lakekeeper met een eigen PostgreSQL, Trino en een Python-container met DuckDB. Niets is van buiten bereikbaar.
2. Richt Lakekeeper in en maakt het warehouse `datafundament` op Garage, zonder STS en zonder remote signing (DF-ADR-002). Lakekeeper controleert daarbij zelf of het op Garage kan schrijven.
3. DuckDB: tabel maken, invoegen met geometrie als WKB, `UPDATE`, `DELETE`, `MERGE INTO`, een kolom toevoegen, teruglezen, snapshots.
4. Trino: dezelfde tabel lezen, met de wijzigingen van DuckDB, geometrie uit WKB, en de snapshots.

Elke stap meldt ✓ of ✗. Bij een fout gaat de proef door, zodat één uitvoer alles laat zien.

## Draaien (op dfc)

```
cd /opt/datafundament/proeven/iceberg-schrijfpad
sudo ./proef.sh
```

De eerste keer haalt hij de images op; reken op een paar minuten. Opruimen, ook alle data:

```
sudo ./proef.sh opruimen
```

Stuur de hele uitvoer door; de versies onderaan gebruiken we om de images vast te pinnen.

## Grenzen

- Geen inlog op Lakekeeper en Trino: dat komt in fase 5 (DF-ADR-012).
- dbt zit er nog niet tussen. dbt-duckdb gebruikt dezelfde DuckDB-functies; dat is de volgende stap als dit werkt.
- Dit is een proef. Hij staat los van de compose-bestanden voor de uitrol.
