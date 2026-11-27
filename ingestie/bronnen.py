"""Ingestie van de bronnen op dfw naar de ruwe laag in Iceberg.

De bronnen zijn de BRP-testdata (vrijBRP) en de synthetische gemeentelijke
bronnen daaromheen (bron/werkbank/). Ze komen op drie manieren binnen, zoals
bij een echte gemeente (DF-ADR-014):

  database  rechtstreeks uit PostgreSQL, incrementeel (brp, bag, woz, mor, sociaal)
  api       via de Zaken-API, een REST-API naar het voorbeeld van ZGW (zaken)
  bestand   via een nachtelijke export in de landingsbucket (belastingen)

Per bron twee lagen (DF-ADR-005):

  ruw_<bron>        insert-only: elke versie van een rij wordt toegevoegd
  ruw_<bron>_stand  upsert op id: de huidige stand van de bron

De databasebronnen komen binnen met echte CDC: de logische replicatie van
PostgreSQL, met een slot per laag (ingestie/cdc.py, DF-ADR-006). De eerste keer,
en met CDC=uit, laadt dlt incrementeel op gewijzigd_op. Tabellen zonder tijdstip
(zoals de codetabel) worden steeds helemaal vervangen.

Configuratie komt uit de omgeving: DLT_WACHTWOORD en BRON_HOST voor de bron,
DESTINATION__FILESYSTEM__* voor Garage en PYICEBERG_CATALOG__DEFAULT__* voor
Lakekeeper (zie compose/compose.yml).
"""

import os

import dlt
from dlt.sources.sql_database import sql_database

from ingestie import iceberg_upsert  # noqa: F401  pylint: disable=unused-import

BRONNEN = {
    "brp": dict(
        omschrijving="testdata vrijBRP (Basisregistratie Personen)",
        tabellen=["persoonslijst", "persoon", "ouder_1", "ouder_2", "nationaliteit", "huwelijk",
                  "overlijden", "inschrijving", "verblijfplaats", "kind", "verblijfstitel",
                  "gezag", "reisdocument", "kiesrecht", "diversen", "woningkaart",
                  "lokale_afnemersindicatie"],
        vervangen={"codetabel": ["element", "code"]},
    ),
    "bag": dict(
        omschrijving="synthetische BAG, passend op de adressen in de BRP",
        tabellen=["woonplaats", "openbare_ruimte", "nummeraanduiding", "pand", "verblijfsobject"],
    ),
    "woz": dict(
        omschrijving="synthetische WOZ-administratie",
        tabellen=["object", "waarde", "belanghebbende"],
    ),
    "belastingen": dict(
        soort="bestand",
        omschrijving="nachtelijke export van het belastingsysteem (CSV in de landingsbucket)",
        tabellen=["aanslag"],
    ),
    "mor": dict(
        omschrijving="synthetische meldingen openbare ruimte",
        tabellen=["melding", "status"],
    ),
    "zaken": dict(
        soort="api",
        omschrijving="Zaken-API van het zaaksysteem (naar het voorbeeld van ZGW)",
        tabellen=["zaken", "statussen", "rollen", "zaakobjecten"],
        vervangen={"zaaktypen": "url"},
    ),
    "sociaal": dict(
        omschrijving="synthetisch sociaal domein: Wmo, Jeugd, Participatiewet (art. 9 AVG)",
        tabellen=["wmo_voorziening", "jeugdhulp_traject", "participatiewet_uitkering"],
    ),
}


def lagen(bron):
    """De twee ruwe lagen van een bron, met hun schrijfwijze."""
    return {
        f"ruw_{bron}": "append",
        f"ruw_{bron}_stand": {"disposition": "merge", "strategy": "upsert"},
    }


def alle_tabellen(bron):
    b = BRONNEN[bron]
    return b["tabellen"] + list(b.get("vervangen", {}))


def bron_url():
    return (f"postgresql+psycopg2://dlt_lezer:{os.environ['DLT_WACHTWOORD']}"
            f"@{os.environ.get('BRON_HOST', '10.67.0.2')}:{os.environ.get('BRON_POORT', '5432')}/bron")


def bron_dsn():
    return (f"host={os.environ.get('BRON_HOST', '10.67.0.2')} port={os.environ.get('BRON_POORT', '5432')} "
            f"dbname=bron user=dlt_lezer "
            f"password={os.environ['DLT_WACHTWOORD']}")


def pseudonimiseer(src, bron, kluis=None):
    """Pseudoniemen in plaats van BSN's, en namen en A-nummers eruit (DF-ADR-015)."""
    from ingestie import pseudoniem  # pylint: disable=import-outside-toplevel
    k = None
    resources = src.resources.values() if hasattr(src, "resources") else [src]
    for res in resources:
        if not pseudoniem.regels(bron, res.name):
            continue
        k = k or kluis or pseudoniem.Kluis()
        res.add_map(pseudoniem.pseudonimiseer(bron, res.name, k)).add_filter(lambda i: i is not None)
    return src


def source(bron, laag, kluis=None):
    """De bron als dlt-source, met de schrijfwijze van de laag, gepseudonimiseerd."""
    return pseudonimiseer(_source(bron, laag), bron, kluis)


def _source(bron, laag):
    soort = BRONNEN[bron].get("soort", "database")
    if soort == "api":
        from ingestie import zaken_api  # pylint: disable=import-outside-toplevel
        return zaken_api.source(lagen(bron)[laag])
    if soort == "bestand":
        from ingestie import landing  # pylint: disable=import-outside-toplevel
        return landing.source(laag, stand=laag.endswith("_stand"))
    b = BRONNEN[bron]
    from ingestie import pseudoniem  # pylint: disable=import-outside-toplevel
    src = sql_database(bron_url(), schema=bron, table_names=alle_tabellen(bron),
                       table_adapter_callback=alles_mag_leeg(pseudoniem.tabel_adapter(bron)),
                       query_adapter_callback=pseudoniem.query_adapter(bron))
    from ingestie import cdc  # pylint: disable=import-outside-toplevel
    for t in b["tabellen"]:
        getattr(src, t).apply_hints(
            primary_key="id",
            incremental=dlt.sources.incremental("gewijzigd_op"),
            write_disposition=lagen(bron)[laag],
            columns=cdc.KOLOMMEN if laag == f"ruw_{bron}" else cdc.KOLOMMEN[1:],
        )
    for t, sleutel in b.get("vervangen", {}).items():
        getattr(src, t).apply_hints(primary_key=sleutel, write_disposition="replace")
    return src


def pijplijn(bron, laag):
    return dlt.pipeline(f"{bron}_{laag}", destination="filesystem", dataset_name=laag)


def cdc_aan(bron):
    return BRONNEN[bron].get("soort", "database") == "database" and os.environ.get("CDC", "aan") != "uit"


def alles_mag_leeg(adapter):
    """Alle kolommen behalve de sleutel mogen leeg zijn: een verwijdering via CDC
    komt binnen met alleen het id (DF-ADR-006)."""
    def aanpassen(tabel):
        tabel = adapter(tabel)
        for kolom in tabel.columns:
            if not kolom.primary_key:
                kolom.nullable = True
        return tabel
    return aanpassen


def laad(bron, laag, kluis=None):
    """Laadt één laag van één bron. Geeft (rijen per tabel, verslag) terug."""
    if not cdc_aan(bron):
        return laad_incrementeel(bron, laag, kluis), {"slot": "uit"}
    import psycopg2  # pylint: disable=import-outside-toplevel
    from ingestie import cdc, pseudoniem  # pylint: disable=import-outside-toplevel
    b = BRONNEN[bron]
    k = kluis or (pseudoniem.Kluis() if bron in pseudoniem.REGELS else None)
    con = psycopg2.connect(bron_dsn())
    try:
        rijen, verslag = cdc.laad(
            bron, laag, con, pijplijn(bron, laag),
            pseudonimiseer=lambda r: pseudonimiseer(r, bron, k),
            tabellen=b["tabellen"],
            incrementeel=lambda: laad_incrementeel(bron, laag, k))
    finally:
        con.close()
    # De vervangen tabellen (codetabel) zitten niet in de replicatie: die steeds helemaal.
    if b.get("vervangen") and verslag["slot"] != "aangemaakt":
        rijen.update(laad_incrementeel(bron, laag, k, alleen_vervangen=True))
    return rijen, verslag


def laad_incrementeel(bron, laag, kluis=None, alleen_vervangen=False):
    """Incrementeel op gewijzigd_op (of uit de API of het bestand). Rijen per tabel."""
    pijp = pijplijn(bron, laag)
    src = source(bron, laag, kluis)
    if alleen_vervangen:
        src = src.with_resources(*BRONNEN[bron]["vervangen"])
    info = pijp.run(src, table_format="iceberg")
    info.raise_on_failed_jobs()
    norm = pijp.last_trace.last_normalize_info
    rijen = norm.row_counts if norm else {}
    namen = list(BRONNEN[bron]["vervangen"]) if alleen_vervangen else alle_tabellen(bron)
    return {t: rijen.get(t, 0) for t in namen}
