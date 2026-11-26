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

dlt laadt incrementeel op gewijzigd_op (DF-ADR-006). Tabellen zonder tijdstip
(zoals de codetabel) worden steeds helemaal vervangen.

Configuratie komt uit de omgeving: DLT_WACHTWOORD en BRON_HOST voor de bron,
DESTINATION__FILESYSTEM__* voor Garage en PYICEBERG_CATALOG__DEFAULT__* voor
Lakekeeper (zie compose/compose.yml).
"""

import os

import dlt
from dlt.sources.sql_database import sql_database

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
            f"@{os.environ.get('BRON_HOST', '10.67.0.2')}:5432/bron")


def source(bron, laag):
    """De bron als dlt-source, met de schrijfwijze van de laag."""
    soort = BRONNEN[bron].get("soort", "database")
    if soort == "api":
        from ingestie import zaken_api  # pylint: disable=import-outside-toplevel
        return zaken_api.source(lagen(bron)[laag])
    if soort == "bestand":
        from ingestie import landing  # pylint: disable=import-outside-toplevel
        return landing.source(laag, stand=laag.endswith("_stand"))
    b = BRONNEN[bron]
    src = sql_database(bron_url(), schema=bron, table_names=alle_tabellen(bron))
    for t in b["tabellen"]:
        getattr(src, t).apply_hints(
            primary_key="id",
            incremental=dlt.sources.incremental("gewijzigd_op"),
            write_disposition=lagen(bron)[laag],
        )
    for t, sleutel in b.get("vervangen", {}).items():
        getattr(src, t).apply_hints(primary_key=sleutel, write_disposition="replace")
    return src


def laad(bron, laag):
    """Laadt één laag van één bron. Geeft het aantal geladen rijen per tabel terug."""
    pijp = dlt.pipeline(f"{bron}_{laag}", destination="filesystem", dataset_name=laag)
    info = pijp.run(source(bron, laag), table_format="iceberg")
    info.raise_on_failed_jobs()
    norm = pijp.last_trace.last_normalize_info
    rijen = norm.row_counts if norm else {}
    return {t: rijen.get(t, 0) for t in alle_tabellen(bron)}
