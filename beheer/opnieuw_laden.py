"""De ruwe lagen en de uniforme laag leegmaken, zodat de ingestie alles opnieuw laadt.

Eén keer nodig bij de overstap naar pseudoniemen (DF-ADR-015): de lagen van
daarvoor bevatten nog BSN's en namen. Daarna niet meer; gebruik voor één
persoon een verwijderverzoek in het portaal.

    python -m beheer.opnieuw_laden --ja

Gooit in Lakekeeper alle tabellen weg in ruw_* (behalve ruw_pdok, geen
persoonsgegevens) en uniform, met purge: ook de bestanden in Garage gaan weg.
En wist de staat van dlt, zodat de volgende ingestie bij het begin begint, en
de replicatieslots op de bron (df_ruw_*): de volgende ingestie maakt ze opnieuw
en laadt dan eerst alles (DF-ADR-006).
"""

import os
import shutil
import sys

from pyiceberg.catalog import load_catalog


def leegmaken():
    catalogus = load_catalog("default")
    weg = 0
    for ns in catalogus.list_namespaces():
        naam = ".".join(ns)
        if not ((naam.startswith("ruw_") and naam != "ruw_pdok") or naam == "uniform"):
            continue
        for ident in catalogus.list_tables(ns):
            catalogus.purge_table(ident)
            weg += 1
        print(f"  {naam}: leeg")
    pijpen = os.path.join(os.environ.get("DLT_DATA_DIR", "/var/lib/dlt"), "pipelines")
    gewist = 0
    if os.path.isdir(pijpen):
        for p in os.listdir(pijpen):
            if "_ruw_" in p:
                shutil.rmtree(os.path.join(pijpen, p))
                gewist += 1
    slots = slots_weg()
    print(f"{weg} tabellen weg (met bestanden); staat van {gewist} dlt-pijplijnen gewist; {slots} replicatieslots weg.")
    print("De volgende ingestie (elke 5 minuten) laadt alles opnieuw, met pseudoniemen.")


def slots_weg():
    """De replicatieslots van de ingestie op de bron weggooien."""
    if not os.environ.get("DLT_WACHTWOORD"):
        return 0
    import psycopg2  # pylint: disable=import-outside-toplevel
    from ingestie import bronnen  # pylint: disable=import-outside-toplevel
    with psycopg2.connect(bronnen.bron_dsn()) as con, con.cursor() as cur:
        cur.execute("SELECT count(pg_drop_replication_slot(slot_name)) FROM pg_replication_slots "
                    "WHERE slot_name LIKE 'df\\_ruw\\_%' AND NOT active")
        return cur.fetchone()[0]


if __name__ == "__main__":
    if "--ja" not in sys.argv:
        raise SystemExit("Dit gooit de ruwe lagen en de uniforme laag weg. Bevestig met: --ja")
    leegmaken()
