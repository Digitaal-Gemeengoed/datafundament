"""Ingestie van de bron (BRP-testdata op dfw) naar de ruwe laag in Iceberg.

Twee vormen (DF-ADR-005):
  ruw_brp        insert-only: elke versie van een rij wordt toegevoegd; nooit iets overschreven
  ruw_brp_stand  upsert op id: de huidige stand van de bron

dlt laadt incrementeel op gewijzigd_op (DF-ADR-006). De codetabel heeft geen
tijdstip en wordt steeds helemaal vervangen.

Configuratie komt uit de omgeving: DLT_WACHTWOORD en BRON_HOST voor de bron,
DESTINATION__FILESYSTEM__* voor Garage en PYICEBERG_CATALOG__DEFAULT__* voor
Lakekeeper (zie compose/compose.yml).
"""

import os

import dlt
from dlt.sources.sql_database import sql_database

# De tabellen van de bron (bron/sql/02-schema.sql), behalve de codetabel.
TABELLEN = [
    "persoonslijst", "persoon", "ouder_1", "ouder_2", "nationaliteit", "huwelijk",
    "overlijden", "inschrijving", "verblijfplaats", "kind", "verblijfstitel",
    "gezag", "reisdocument", "kiesrecht", "diversen", "woningkaart",
    "lokale_afnemersindicatie",
]
ALLE_TABELLEN = TABELLEN + ["codetabel"]

LAGEN = {
    "ruw_brp": "append",
    "ruw_brp_stand": {"disposition": "merge", "strategy": "upsert"},
}


def bron_url():
    return (f"postgresql+psycopg2://dlt_lezer:{os.environ['DLT_WACHTWOORD']}"
            f"@{os.environ.get('BRON_HOST', '10.67.0.2')}:5432/bron")


def bron(laag):
    """De bron als dlt-source, met de schrijfwijze van de laag."""
    src = sql_database(bron_url(), schema="brp", table_names=ALLE_TABELLEN)
    for t in TABELLEN:
        getattr(src, t).apply_hints(
            primary_key="id",
            incremental=dlt.sources.incremental("gewijzigd_op"),
            write_disposition=LAGEN[laag],
        )
    src.codetabel.apply_hints(primary_key=["element", "code"], write_disposition="replace")
    return src


def laad(laag):
    """Laadt één laag. Geeft het aantal geladen rijen per tabel terug."""
    pijp = dlt.pipeline(f"brp_{laag}", destination="filesystem", dataset_name=laag)
    info = pijp.run(bron(laag), table_format="iceberg")
    info.raise_on_failed_jobs()
    norm = pijp.last_trace.last_normalize_info
    rijen = norm.row_counts if norm else {}
    return {t: rijen.get(t, 0) for t in ALLE_TABELLEN}
