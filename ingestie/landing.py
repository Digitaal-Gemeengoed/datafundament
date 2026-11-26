"""Bestanden uit de landingsbucket als bron voor dlt (DF-ADR-014).

Een leverancier zet elke nacht een export in de bucket 'landing' in Garage
(op dfw: bron.sh export-belastingen). dlt leest alleen de bestanden die er
sinds de vorige keer bij zijn gekomen, en neemt ze over zoals ze zijn: alles
als tekst, met de naam van het bestand erbij. Datums, bedragen met een komma
en kopjes in gewone taal worden pas in dbt uniform gemaakt.

  ruw_belastingen        elke regel uit elk bestand (de aanlevering zelf)
  ruw_belastingen_stand  per aanslag de laatst aangeleverde regel
"""

import csv
import io
import os
import re

import dlt
import fsspec

MAP = "landing/belastingen/aanslag"


def kolom(kop):
    return re.sub(r"[^a-z0-9]+", "_", kop.strip().lower()).strip("_")


def bestandssysteem():
    """De landingsbucket in Garage, of voor tests een lokale map (LANDING_MAP)."""
    if os.environ.get("LANDING_MAP"):
        return fsspec.filesystem("file"), os.environ["LANDING_MAP"]
    return fsspec.filesystem(
        "s3", key=os.environ["GARAGE_SCHRIJVER_SLEUTEL"], secret=os.environ["GARAGE_SCHRIJVER_GEHEIM"],
        client_kwargs={"endpoint_url": os.environ.get("LANDING_ENDPOINT", "http://garage:3900"),
                       "region_name": "garage"},
        config_kwargs={"s3": {"addressing_style": "path"}}), MAP


def source(laag, stand=False):
    @dlt.resource(name="aanslag", primary_key="aanslagnummer",
                  write_disposition={"disposition": "merge", "strategy": "upsert"} if stand else "append")
    def aanslag():
        fs, map_ = bestandssysteem()
        gelezen = dlt.current.resource_state().setdefault("gelezen", [])
        nieuw = sorted(p for p in fs.ls(map_, detail=False, refresh=True)
                       if p.endswith(".csv") and os.path.basename(p) not in gelezen)
        laatste = {}
        for pad in nieuw:  # de namen bevatten het tijdstip: oud eerst
            with fs.open(pad, "rb") as f:
                tekst = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
                for regel in csv.DictReader(tekst, delimiter=";"):
                    rij = {kolom(k): v for k, v in regel.items()}
                    rij["bestand"] = os.path.basename(pad)
                    if stand:  # per aanslag alleen de laatst aangeleverde regel
                        laatste[rij["aanslagnummer"]] = rij
                    else:
                        yield rij
            gelezen.append(os.path.basename(pad))
        yield from laatste.values()

    return aanslag
