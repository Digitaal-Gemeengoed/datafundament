"""Proef: dlt leest de bron op dfw (over WireGuard) en schrijft naar Iceberg via Lakekeeper.

Twee vormen van de ruwe laag naast elkaar:
  ruw_brp        insert-only: elke versie van een rij wordt toegevoegd (volledige historie)
  ruw_brp_stand  upsert op id: de huidige stand van de bron

Halverwege vraagt de proef om op dfw een verhuizing te doen; daarna laadt hij
opnieuw en controleert dat de wijziging in beide vormen is aangekomen.
Elke stap meldt ✓ of ✗ en gaat bij een fout door.
"""

import os
import sys

import dlt
import sqlalchemy as sa
from dlt.sources.sql_database import sql_database
from pyiceberg.catalog import load_catalog

BRON = (f"postgresql+psycopg2://dlt_lezer:{os.environ['DLT_WACHTWOORD']}"
        f"@{os.environ.get('BRON_HOST', '10.67.0.2')}:5432/bron")
TABELLEN = ["persoonslijst", "persoon", "verblijfplaats"]
BSN = os.environ.get("PROEF_BSN", "999997889")

fouten = []


def stap(naam, actie):
    try:
        uitkomst = actie()
        print(f"  ✓ {naam}")
        return uitkomst
    except Exception as e:  # noqa: BLE001 — de proef meldt elke fout en gaat door
        print(f"  ✗ {naam}\n      {type(e).__name__}: {str(e).strip()[:800]}")
        fouten.append(naam)
        return None


def bron_tabellen(schrijfwijze):
    bron = sql_database(BRON, schema="brp", table_names=TABELLEN)
    for t in TABELLEN:
        getattr(bron, t).apply_hints(
            primary_key="id",
            incremental=dlt.sources.incremental("gewijzigd_op"),
            write_disposition=schrijfwijze,
        )
    return bron


PIJPEN = {
    "ruw_brp": "append",
    "ruw_brp_stand": {"disposition": "merge", "strategy": "upsert"},
}


def laad(dataset):
    pijp = dlt.pipeline(f"proef_{dataset}", destination="filesystem", dataset_name=dataset)
    info = pijp.run(bron_tabellen(PIJPEN[dataset]), table_format="iceberg")
    if info.has_failed_jobs:
        raise RuntimeError(str(info))
    rijen = pijp.last_trace.last_normalize_info.row_counts if pijp.last_trace.last_normalize_info else {}
    return {t: n for t, n in rijen.items() if not t.startswith("_dlt")}


def iceberg_rijen(catalogus, dataset, tabel, pl_id=None):
    t = catalogus.load_table((dataset, tabel))
    scan = t.scan(row_filter=f"pl_id == {pl_id}") if pl_id else t.scan()
    return scan.to_arrow()


print("\n== Bron op dfw, over WireGuard")
motor = sa.create_engine(BRON)


def bron_info():
    with motor.connect() as c:
        wie = c.execute(sa.text("SELECT inet_client_addr()::text, current_user")).one()
        n = c.execute(sa.text("SELECT count(*) FROM brp.verblijfplaats")).scalar()
        pl = c.execute(sa.text("SELECT id FROM brp.persoonslijst WHERE burgerservicenummer = :b"), {"b": BSN}).scalar()
    return wie, n, pl


info = stap("Verbinden als dlt_lezer en lezen", bron_info)
pl_id = None
if info:
    (adres, gebruiker), n, pl_id = info
    print(f"      bron ziet ons als {gebruiker} vanaf {adres}; brp.verblijfplaats: {n} rijen; BSN {BSN} is pl_id {pl_id}")

print("\n== Iceberg-catalogus (Lakekeeper)")
catalogus = stap("Catalogus laden met pyiceberg", lambda: load_catalog("default"))

print("\n== Eerste lading")
for ds in PIJPEN:
    r = stap(f"{ds}: laden ({PIJPEN[ds] if isinstance(PIJPEN[ds], str) else 'upsert'})", lambda ds=ds: laad(ds))
    if r is not None:
        print(f"      {r}")

voor = {}
if catalogus:
    for ds in PIJPEN:
        a = stap(f"{ds}: verblijfplaats teruglezen", lambda ds=ds: iceberg_rijen(catalogus, ds, "verblijfplaats"))
        voor[ds] = a.num_rows if a is not None else None
        print(f"      {voor[ds]} rijen")

print()
print(f"  → Voer nu op dfw uit:  cd /opt/datafundament/bron && sudo ./bron.sh verhuis {BSN}")
try:
    input("    Druk daarna hier op Enter. ")
except EOFError:
    print("    (geen invoer mogelijk; ik ga verder zonder te wachten)")

print("\n== Tweede lading, na de verhuizing")
for ds in PIJPEN:
    r = stap(f"{ds}: alleen de wijzigingen laden", lambda ds=ds: laad(ds))
    if r is not None:
        print(f"      {r}")

if catalogus and pl_id:
    def controle(ds, verwacht_extra):
        def doe():
            alles = iceberg_rijen(catalogus, ds, "verblijfplaats")
            persoon = iceberg_rijen(catalogus, ds, "verblijfplaats", pl_id).sort_by("id").to_pylist()
            for r in persoon:
                print(f"      id {r['id']}, volgnr {r['volgnr']}, actueel {r['actueel']}, "
                      f"{r['straatnaam']} {r['huisnummer']}, gewijzigd {r['gewijzigd_op']}")
            if voor.get(ds) is not None and alles.num_rows != voor[ds] + verwacht_extra:
                raise AssertionError(f"verwacht {voor[ds]} + {verwacht_extra} rijen, er zijn er {alles.num_rows}")
            if sum(1 for r in persoon if r["actueel"]) < 1:
                raise AssertionError("geen actueel adres gevonden")
        return doe

    stap("ruw_brp: oude adres als nieuwe versie (actueel=false) én nieuw adres toegevoegd (+2)",
         controle("ruw_brp", 2))
    stap("ruw_brp_stand: oude adres bijgewerkt, nieuw adres erbij (+1)",
         controle("ruw_brp_stand", 1))

print()
if fouten:
    print(f"dlt-deel: {len(fouten)} stap(pen) mislukt: {', '.join(fouten)}")
    sys.exit(1)
print("dlt-deel: alle stappen gelukt.")
