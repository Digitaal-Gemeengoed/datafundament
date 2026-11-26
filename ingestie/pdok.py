"""Geodata van PDOK naar de ruwe laag (ruw_pdok), met dlt.

  adres_locatie  de actuele adressen uit de bron, opgezocht in de Locatieserver
                 (BAG): coördinaten in RD en buurtcode. Alleen adressen die nog
                 niet zijn opgezocht; upsert op de sleutel postcode|huisnummer|huisletter.
  cbs_buurten    CBS Wijken en Buurten 2025 (CC-BY 4.0), alleen de gemeenten
                 waar de testpersonen volgens de Locatieserver wonen; met kerncijfers.

Beide lezen de adressen uit het lakehouse (ruw_brp_stand), niet uit de bron.
"""

import json
import time
from datetime import datetime, timezone

import dlt
import requests
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchNamespaceError, NoSuchTableError

LOCATIESERVER = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
CBS_BUURTEN = "https://api.pdok.nl/cbs/wijken-en-buurten-2025/ogc/v1/collections/buurten/items"
RD = "http://www.opengis.net/def/crs/EPSG/0/28992"
VELDEN = ("weergavenaam", "centroide_rd", "buurtcode", "buurtnaam", "wijkcode", "wijknaam",
          "gemeentecode", "gemeentenaam", "nummeraanduiding_id", "adresseerbaarobject_id")
DATASET = "ruw_pdok"


def _tabel(catalogus, namespace, tabel):
    try:
        return catalogus.load_table((namespace, tabel))
    except (NoSuchTableError, NoSuchNamespaceError):
        return None


def sleutel(postcode, huisnummer, huisletter):
    return f"{postcode}|{huisnummer}|{huisletter or ''}"


def nieuwe_adressen():
    """Actuele adressen uit ruw_brp_stand die nog niet in ruw_pdok.adres_locatie staan."""
    cat = load_catalog("default")
    vbp = _tabel(cat, "ruw_brp_stand", "verblijfplaats")
    if vbp is None:
        return []
    rijen = vbp.scan(row_filter="actueel == true",
                     selected_fields=("postcode", "huisnummer", "huisletter")).to_arrow().to_pylist()
    al = set()
    bekend = _tabel(cat, DATASET, "adres_locatie")
    if bekend is not None:
        al = {r["sleutel"] for r in bekend.scan(selected_fields=("sleutel",)).to_arrow().to_pylist()}
    uniek = {}
    for r in rijen:
        if r["postcode"] and r["huisnummer"]:
            k = sleutel(r["postcode"], r["huisnummer"], r["huisletter"])
            if k not in al:
                uniek[k] = r
    return list(uniek.items())


@dlt.resource(name="adres_locatie", primary_key="sleutel",
              write_disposition={"disposition": "merge", "strategy": "upsert"})
def adres_locatie():
    sessie = requests.Session()
    for k, r in nieuwe_adressen():
        q = f"postcode:{r['postcode']} AND huisnummer:{r['huisnummer']}"
        if r["huisletter"]:
            q += f" AND huisletter:{r['huisletter']}"
        antwoord = sessie.get(LOCATIESERVER, params={"q": q, "fq": "type:adres", "rows": 1,
                                                    "fl": ",".join(VELDEN)}, timeout=20)
        antwoord.raise_for_status()
        docs = antwoord.json()["response"]["docs"]
        rij = {"sleutel": k, "postcode": r["postcode"], "huisnummer": r["huisnummer"],
               "huisletter": r["huisletter"] or None, "gevonden": bool(docs),
               "opgevraagd_op": datetime.now(timezone.utc)}
        rij.update({v: (docs[0].get(v) if docs else None) for v in VELDEN})
        yield rij
        time.sleep(0.05)  # vriendelijk voor PDOK


def gemeenten_van_adressen():
    bekend = _tabel(load_catalog("default"), DATASET, "adres_locatie")
    if bekend is None:
        return []
    rijen = bekend.scan(selected_fields=("gemeentecode",)).to_arrow().to_pylist()
    return sorted({r["gemeentecode"] for r in rijen if r["gemeentecode"]})


@dlt.resource(name="cbs_buurten", primary_key="buurtcode", write_disposition="replace")
def cbs_buurten():
    sessie = requests.Session()
    for gemeente in gemeenten_van_adressen():
        url = CBS_BUURTEN
        params = {"f": "json", "gemeentecode": f"GM{gemeente}", "limit": 1000, "crs": RD}
        while url:
            antwoord = sessie.get(url, params=params, timeout=60)
            antwoord.raise_for_status()
            crs = antwoord.headers.get("Content-Crs", "").strip("<>")
            data = antwoord.json()
            for f in data.get("features", []):
                rij = dict(f.get("properties", {}))
                rij["geometrie_geojson"] = json.dumps(f.get("geometry"))
                rij["crs"] = crs or "onbekend"
                yield rij
            url = next((l["href"] for l in data.get("links", []) if l.get("rel") == "next"), None)
            params = None  # de next-link bevat de parameters al


def laad(resource):
    pijp = dlt.pipeline("pdok", destination="filesystem", dataset_name=DATASET)
    info = pijp.run(resource(), table_format="iceberg")
    info.raise_on_failed_jobs()
    norm = pijp.last_trace.last_normalize_info
    return (norm.row_counts if norm else {}).get(resource.name, 0)
