"""De ruwe lagen en de uniforme laag leegmaken, zodat de ingestie alles opnieuw laadt.

Eén keer nodig bij de overstap naar pseudoniemen (DF-ADR-015): de lagen van
daarvoor bevatten nog BSN's en namen. Daarna niet meer; gebruik voor één
persoon een verwijderverzoek in het portaal.

    python -m beheer.opnieuw_laden --ja

Gooit in Lakekeeper alle tabellen weg in ruw_* (behalve ruw_pdok, geen
persoonsgegevens) en uniform, met purge: ook de bestanden in Garage gaan weg.
En wist de staat van dlt, zodat de volgende ingestie bij het begin begint.
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
    print(f"{weg} tabellen weg (met bestanden); staat van {gewist} dlt-pijplijnen gewist.")
    print("De volgende ingestie (elke 5 minuten) laadt alles opnieuw, met pseudoniemen.")


if __name__ == "__main__":
    if "--ja" not in sys.argv:
        raise SystemExit("Dit gooit de ruwe lagen en de uniforme laag weg. Bevestig met: --ja")
    leegmaken()
