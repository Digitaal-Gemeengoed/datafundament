"""Onderhoud van het lakehouse: oude snapshots van Iceberg-tabellen opruimen.

Elke ingestie en elke dbt-run maakt een snapshot. Met de simulatieklok en een
ingestie om de vijf minuten zijn dat er per tabel tienduizenden per jaar; de
metadata groeit daarmee mee en wordt traag. De ruwe laag is insert-only en
heeft de snapshots niet nodig voor historie (DF-ADR-005); time travel van een
week is genoeg.

Wat dit nog niet doet (DF-ADR-014): kleine bestanden samenvoegen (compaction)
en bestanden opruimen waar geen snapshot meer naar verwijst. pyiceberg kan dat
nog niet; daarvoor is een schrijvende engine nodig (Spark, of Trino met een
eigen onderhoudscatalogus).

    python -m beheer.onderhoud [DAGEN]
"""

import sys
import time

from pyiceberg.catalog import load_catalog


def snapshots_opruimen(dagen=7, log=print):
    catalogus = load_catalog("default")  # PYICEBERG_CATALOG__DEFAULT__* uit de omgeving
    grens = int((time.time() - dagen * 86400) * 1000)
    totaal = {}
    for ns in catalogus.list_namespaces():
        for ident in catalogus.list_tables(ns):
            tabel = catalogus.load_table(ident)
            huidig = tabel.current_snapshot()
            oud = [s.snapshot_id for s in tabel.snapshots()
                   if s.timestamp_ms < grens and (huidig is None or s.snapshot_id != huidig.snapshot_id)]
            if oud:
                tabel.maintenance.expire_snapshots().by_ids(oud).commit()
                totaal[".".join(ident)] = len(oud)
    log(f"{sum(totaal.values())} snapshots ouder dan {dagen} dagen opgeruimd in {len(totaal)} tabellen")
    return totaal


def alle_oude_snapshots_weg(idents, log=print):
    """Alle snapshots behalve de huidige, in de genoemde tabellen (na een verwijdering)."""
    catalogus = load_catalog("default")
    totaal = 0
    for ident in idents:
        tabel = catalogus.load_table(tuple(ident))
        huidig = tabel.current_snapshot()
        oud = [s.snapshot_id for s in tabel.snapshots() if huidig is None or s.snapshot_id != huidig.snapshot_id]
        if oud:
            tabel.maintenance.expire_snapshots().by_ids(oud).commit()
            totaal += len(oud)
    log(f"{totaal} oude snapshots opgeruimd in {len(idents)} tabellen")
    return totaal


if __name__ == "__main__":
    snapshots_opruimen(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
