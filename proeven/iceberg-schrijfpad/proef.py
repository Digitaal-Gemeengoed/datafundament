"""Proef DF-ADR-004: DuckDB schrijft naar Iceberg via Lakekeeper, op Garage.

Elke stap meldt ✓ of ✗ met de foutmelding, en gaat bij een fout door, zodat
één uitvoer laat zien wat wel en niet werkt. Draait in de container 'proef'.
"""

import os
import sys
import time

import duckdb
import requests

LAKEKEEPER = "http://lakekeeper:8181"
WAREHOUSE = "datafundament"
SLEUTEL = os.environ["GARAGE_SLEUTEL"]
GEHEIM = os.environ["GARAGE_GEHEIM"]

fouten = []


def stap(naam, actie):
    try:
        uitkomst = actie()
        print(f"  ✓ {naam}")
        return uitkomst
    except Exception as e:  # noqa: BLE001 — de proef meldt elke fout en gaat door
        print(f"  ✗ {naam}\n      {type(e).__name__}: {str(e).strip()[:600]}")
        fouten.append(naam)
        return None


def wacht_op_lakekeeper():
    for _ in range(60):
        try:
            # Elk antwoord onder 500 betekent: de server luistert.
            if requests.get(f"{LAKEKEEPER}/health", timeout=2).status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError("Lakekeeper antwoordt niet na 2 minuten")


def bootstrap():
    r = requests.post(f"{LAKEKEEPER}/management/v1/bootstrap",
                      json={"accept-terms-of-use": True}, timeout=10)
    # Al gedaan bij een eerdere run: dat is goed.
    if not r.ok and "already" not in r.text.lower():
        raise RuntimeError(f"{r.status_code} {r.text}")


def versie():
    r = requests.get(f"{LAKEKEEPER}/management/v1/info", timeout=10)
    r.raise_for_status()
    return r.json().get("version", "?")


def warehouse():
    r = requests.get(f"{LAKEKEEPER}/management/v1/warehouse", timeout=10)
    if r.ok and any(w.get("name") == WAREHOUSE for w in r.json().get("warehouses", [])):
        return "bestond al"
    profiel = {
        "type": "s3",
        "bucket": "lakehouse",
        "key-prefix": "warehouse",
        "region": "garage",
        "endpoint": "http://garage:3900",
        "path-style-access": True,
        "flavor": "s3-compat",
        # Garage kent geen STS; de engines krijgen een eigen sleutel (DF-ADR-002).
        "sts-enabled": False,
        "remote-signing-enabled": False,
    }
    body = {
        "warehouse-name": WAREHOUSE,
        "storage-profile": profiel,
        "storage-credential": {
            "type": "s3",
            "credential-type": "access-key",
            "aws-access-key-id": SLEUTEL,
            "aws-secret-access-key": GEHEIM,
        },
    }
    r = requests.post(f"{LAKEKEEPER}/management/v1/warehouse", json=body, timeout=30)
    if not r.ok and "remote-signing-enabled" in r.text:
        # Oudere Lakekeeper kent dit veld niet; zonder proberen.
        del profiel["remote-signing-enabled"]
        r = requests.post(f"{LAKEKEEPER}/management/v1/warehouse", json=body, timeout=30)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text}")
    return "aangemaakt (Lakekeeper heeft schrijven en lezen op Garage gecontroleerd)"


print("\n== Lakekeeper en Garage")
stap("Lakekeeper antwoordt", wacht_op_lakekeeper)
stap("Lakekeeper ingericht (bootstrap)", bootstrap)
print(f"    Lakekeeper-versie: {stap('Versie opvragen', versie)}")
print(f"    Warehouse: {stap('Warehouse op Garage', warehouse)}")

print(f"\n== DuckDB {duckdb.__version__}")
con = duckdb.connect()
q = con.execute
stap("Extensies iceberg, httpfs en spatial", lambda: q(
    "INSTALL iceberg; LOAD iceberg; INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;"))
stap("Sleutel voor Garage (S3, path-style)", lambda: q(f"""
    CREATE SECRET garage (TYPE s3, KEY_ID '{SLEUTEL}', SECRET '{GEHEIM}',
      ENDPOINT 'garage:3900', URL_STYLE 'path', USE_SSL false, REGION 'garage')"""))
def aankoppelen():
    opties = [
        "AUTHORIZATION_TYPE 'none', ACCESS_DELEGATION_MODE 'none'",
        "AUTHORIZATION_TYPE 'none'",  # als deze DuckDB ACCESS_DELEGATION_MODE niet kent
    ]
    laatste = None
    for o in opties:
        try:
            q(f"ATTACH '{WAREHOUSE}' AS lk (TYPE iceberg, ENDPOINT '{LAKEKEEPER}/catalog', {o})")
            return o
        except duckdb.Error as e:
            laatste = e
    raise laatste


print(f"    Aangekoppeld met: {stap('Catalogus aankoppelen (zonder inlog, zonder vended credentials)', aankoppelen)}")
stap("Schema maken", lambda: q("CREATE SCHEMA IF NOT EXISTS lk.proef"))
stap("Oude proeftabel weg", lambda: q("DROP TABLE IF EXISTS lk.proef.personen"))
stap("Tabel maken, met een kolom voor geometrie als WKB", lambda: q("""
    CREATE TABLE lk.proef.personen (id INTEGER, naam VARCHAR, buurt VARCHAR, locatie BLOB)"""))
stap("Invoegen, met punten in RD (EPSG:28992)", lambda: q("""
    INSERT INTO lk.proef.personen VALUES
      (1, 'Anna Testpersoon',  'Centrum',  ST_AsWKB(ST_Point(103500, 488000))),
      (2, 'Bram Testpersoon',  'Schalkwijk', ST_AsWKB(ST_Point(106000, 485500))),
      (3, 'Cora Testpersoon',  'Noord',    ST_AsWKB(ST_Point(104000, 490500)))"""))
stap("Bijwerken (UPDATE)", lambda: q("UPDATE lk.proef.personen SET buurt = 'Oost' WHERE id = 3"))
stap("Verwijderen (DELETE)", lambda: q("DELETE FROM lk.proef.personen WHERE id = 2"))
stap("MERGE INTO (bijwerken én invoegen)", lambda: q("""
    MERGE INTO lk.proef.personen AS p
    USING (VALUES (1, 'Anna Testpersoon-de Vries', 'Centrum'), (4, 'Daan Testpersoon', 'Zuid')) AS b(id, naam, buurt)
    ON p.id = b.id
    WHEN MATCHED THEN UPDATE SET naam = b.naam
    WHEN NOT MATCHED THEN INSERT (id, naam, buurt, locatie) VALUES (b.id, b.naam, b.buurt, NULL)"""))
stap("Kolom toevoegen (schemawijziging)", lambda: q(
    "ALTER TABLE lk.proef.personen ADD COLUMN geboortejaar INTEGER"))
stap("Invoegen na de schemawijziging", lambda: q(
    "INSERT INTO lk.proef.personen VALUES (5, 'Eva Testpersoon', 'West', NULL, 1990)"))

rijen = stap("Teruglezen, met geometrie uit WKB", lambda: q("""
    SELECT id, naam, buurt, geboortejaar, ST_AsText(ST_GeomFromWKB(locatie))
    FROM lk.proef.personen ORDER BY id""").fetchall())
verwacht = {1: "Anna Testpersoon-de Vries", 3: "Cora Testpersoon", 4: "Daan Testpersoon", 5: "Eva Testpersoon"}
if rijen is not None:
    for r in rijen:
        print(f"      {r}")
    def inhoud_klopt():
        gevonden = {r[0]: r[1] for r in rijen}
        if gevonden != verwacht or not any(r[0] == 3 and r[2] == "Oost" for r in rijen):
            raise AssertionError(f"verwacht {verwacht}, kreeg {gevonden}")

    stap("Inhoud klopt (1 bijgewerkt, 2 weg, 3 in Oost, 4 en 5 erbij)", inhoud_klopt)

snaps = stap("Snapshots opvragen (time travel)", lambda: q(
    "SELECT count(*) FROM iceberg_snapshots(lk.proef.personen)").fetchone()[0])
if snaps is not None:
    print(f"      {snaps} snapshots")

print()
if fouten:
    print(f"DuckDB-deel: {len(fouten)} stap(pen) mislukt: {', '.join(fouten)}")
    sys.exit(1)
print("DuckDB-deel: alle stappen gelukt.")
