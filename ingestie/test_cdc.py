"""Echte CDC tegen een PostgreSQL met wal_level=logical (DF-ADR-006).

    TEST_PG="host=127.0.0.1 port=55432 user=postgres" pytest ingestie/test_cdc.py

Maakt een database `bron` met een kleine BRP en een tabel uit het sociaal domein,
de publicaties zoals op dfw, en laadt met dlt naar Iceberg in een tijdelijke map.
"""

import os
import sys
from pathlib import Path

import pytest

PG = os.environ.get("TEST_PG")
pytestmark = pytest.mark.skipif(not PG, reason="TEST_PG niet gezet")
HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "bron" / "werkbank"))

import publicaties  # noqa: E402  pylint: disable=wrong-import-position


@pytest.fixture(scope="module")
def omgeving(tmp_path_factory):
    import psycopg  # pylint: disable=import-outside-toplevel
    d = tmp_path_factory.mktemp("cdc")
    with psycopg.connect(PG, dbname="postgres", autocommit=True) as con:
        con.execute("SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE database = 'bron'")
        con.execute("DROP DATABASE IF EXISTS bron")
        con.execute("CREATE DATABASE bron")
        con.execute("DO $$ BEGIN CREATE ROLE dlt_lezer LOGIN REPLICATION PASSWORD 'lezer'; "
                    "EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    with psycopg.connect(PG, dbname="bron", autocommit=True) as con:
        con.execute("""
            CREATE SCHEMA brp; CREATE SCHEMA sociaal;
            CREATE TABLE brp.persoon (id serial PRIMARY KEY, pl_id int, burgerservicenummer text, voornamen text,
              geslachtsnaam text, geboortedatum date, gewijzigd_op timestamptz NOT NULL DEFAULT now());
            CREATE TABLE sociaal.wmo_voorziening (id serial PRIMARY KEY, bsn text, soort text, bedrag numeric(10,2),
              gewijzigd_op timestamptz NOT NULL DEFAULT now());
            CREATE TABLE brp.zonder_sleutel (x int);
            INSERT INTO brp.persoon (pl_id, burgerservicenummer, voornamen, geslachtsnaam, geboortedatum) VALUES
              (1, '999990019', 'Jan', 'Jansen', '1970-01-01'), (2, '999990020', 'Piet', 'Pietersen', '1980-02-02'),
              (3, '999990032', 'Klaas', 'Klaassen', '1990-03-03');
            INSERT INTO sociaal.wmo_voorziening (bsn, soort, bedrag) VALUES ('999990019', 'rolstoel', 1234.50),
              ('999990032', 'huishoudelijke hulp', 99.95);
            GRANT CONNECT ON DATABASE bron TO dlt_lezer; GRANT USAGE ON SCHEMA brp, sociaal TO dlt_lezer;
            GRANT SELECT ON ALL TABLES IN SCHEMA brp, sociaal TO dlt_lezer;""")
        with con.cursor() as cur:
            assert publicaties.zet(cur, ["brp", "sociaal", "bag"]) == {"brp": 1, "sociaal": 1, "bag": 0}
    os.environ.update({
        "DLT_WACHTWOORD": "lezer", "BRON_HOST": "127.0.0.1", "BRON_POORT": dict(
            kv.split("=") for kv in PG.split()).get("port", "5432"),
        "DESTINATION__FILESYSTEM__BUCKET_URL": f"file://{d}/lakehouse", "DLT_DATA_DIR": str(d / "dlt"),
        "KLUIS_GEHEIM": "test-geheim", "RUNTIME__LOG_LEVEL": "WARNING",
    })
    os.environ.pop("KLUIS_BAO_ADRES", None)
    os.environ.pop("KLUIS_DSN", None)
    from ingestie import bronnen, pseudoniem  # pylint: disable=import-outside-toplevel
    bronnen.BRONNEN = {"brp": dict(omschrijving="test", tabellen=["persoon"]),
                       "sociaal": dict(omschrijving="test", tabellen=["wmo_voorziening"])}
    return bronnen, pseudoniem.Kluis(), lambda sql: psycopg.connect(PG, dbname="bron", autocommit=True).execute(sql)


def tabel(bronnen, bron, laag, t):
    with bronnen.pijplijn(bron, laag).destination_client() as client:
        df = client.load_open_table("iceberg", t).scan().to_pandas()
    return df.sort_values(["id", "_cdc_lsn"] if "_cdc_lsn" in df.columns else ["id"], na_position="first")


def test_weg_klopt_met_de_pseudonimisering():
    from ingestie import pseudoniem  # pylint: disable=import-outside-toplevel
    for bron in pseudoniem.REGELS.values():
        for r in bron.values():
            assert set((r or {}).get("weg", [])) <= publicaties.WEG


def test_cdc_van_begin_tot_eind(omgeving):
    bronnen, kluis, sql = omgeving
    lagen = [("brp", "ruw_brp"), ("brp", "ruw_brp_stand"), ("sociaal", "ruw_sociaal"), ("sociaal", "ruw_sociaal_stand")]

    # De eerste keer: slot aanmaken en een inhaalslag op gewijzigd_op.
    for b, laag in lagen:
        rijen, verslag = bronnen.laad(b, laag, kluis)
        assert verslag["slot"] == "aangemaakt", verslag
    assert len(tabel(bronnen, "brp", "ruw_brp_stand", "persoon")) == 3
    assert {"_cdc_bewerking", "_cdc_lsn", "_cdc_tijdstip"} <= set(tabel(bronnen, "brp", "ruw_brp", "persoon").columns)

    # Wijzigingen in de bron, ook een verwijdering en twee wijzigingen achter elkaar.
    sql("UPDATE brp.persoon SET geboortedatum = '1970-01-02', voornamen = 'Johannes' WHERE id = 1")
    sql("DELETE FROM brp.persoon WHERE id = 3")
    sql("INSERT INTO brp.persoon (pl_id, burgerservicenummer, voornamen, geslachtsnaam, geboortedatum) "
        "VALUES (4, '999990044', 'Kees', 'Keesman', '2000-04-04')")
    sql("UPDATE brp.persoon SET geboortedatum = '1980-02-03' WHERE id = 2")
    sql("UPDATE brp.persoon SET geboortedatum = '1980-02-04' WHERE id = 2")
    sql("UPDATE sociaal.wmo_voorziening SET bedrag = 1300.00 WHERE id = 1")

    # Wat over de lijn gaat: geen namen.
    import psycopg  # pylint: disable=import-outside-toplevel
    with psycopg.connect(PG, dbname="bron") as con:
        data = b"".join(bytes(r[0]) for r in con.execute(
            "SELECT data FROM pg_logical_slot_peek_binary_changes('df_ruw_brp', NULL, NULL, "
            "'proto_version', '1', 'publication_names', 'df_brp')"))
    assert b"999990044" in data and b"Kees" not in data and b"Johannes" not in data

    for b, laag in lagen:
        rijen, verslag = bronnen.laad(b, laag, kluis)
        assert verslag["slot"] == "gelezen" and verslag["porties"] == 1, verslag

    ruw = tabel(bronnen, "brp", "ruw_brp", "persoon")
    cdc = ruw[ruw["_cdc_bewerking"].notna()]
    assert list(cdc["_cdc_bewerking"]) == ["U", "U", "U", "D", "I"]  # gesorteerd op id, dan LSN
    assert not {"voornamen", "geslachtsnaam", "burgerservicenummer"} & set(ruw.columns)
    assert cdc[cdc["_cdc_bewerking"] == "D"]["pseudoniem"].isna().all()

    stand = tabel(bronnen, "brp", "ruw_brp_stand", "persoon")
    assert list(stand["id"]) == [1, 2, 4]
    assert str(stand.set_index("id").loc[2, "geboortedatum"]) .startswith("1980-02-04")
    p1 = stand.set_index("id").loc[1, "pseudoniem"]
    assert p1 == kluis.pseudoniem("999990019")  # hetzelfde pseudoniem als bij de inhaalslag
    wmo = tabel(bronnen, "sociaal", "ruw_sociaal_stand", "wmo_voorziening").set_index("id")
    assert float(wmo.loc[1, "bedrag"]) == 1300.0 and wmo.loc[1, "pseudoniem"] == p1

    # De tijdlijn zoals in uniform/verblijfplaats_historie: de verwijdering sluit hem af.
    import duckdb  # pylint: disable=import-outside-toplevel
    model = (HIER.parent / "transformatie/models/uniform/verblijfplaats_historie.sql").read_text()
    ctes = model[model.index("with versies"):model.index("gemeenten as (")].rstrip().rstrip(",")
    ctes = ctes.replace("{{ source('ruw_brp', 'verblijfplaats') }}", "ruw")
    lijn = duckdb.sql(ctes + " select id, volgende is null from uniek order by id, moment").fetchall()
    assert (3, True) not in lijn and (3, False) in lijn  # persoon 3: tijdlijn afgesloten
    assert lijn.count((2, True)) == 1

    # Niets gewijzigd: niets te doen.
    rijen, verslag = bronnen.laad("brp", "ruw_brp", kluis)
    assert verslag["porties"] == 0 and sum(rijen.values()) == 0


def test_nieuwe_kolom_komt_door_na_de_publicatie(omgeving):
    bronnen, kluis, sql = omgeving
    sql("ALTER TABLE brp.persoon ADD COLUMN indicatie_digitaal_contact text")
    sql("UPDATE brp.persoon SET indicatie_digitaal_contact = 'N' WHERE id = 1")  # nog niet in de publicatie
    import psycopg  # pylint: disable=import-outside-toplevel
    with psycopg.connect(PG, dbname="bron", autocommit=True) as con, con.cursor() as cur:
        publicaties.zet(cur, ["brp"])
    sql("UPDATE brp.persoon SET indicatie_digitaal_contact = 'J' WHERE id = 2")
    bronnen.laad("brp", "ruw_brp", kluis)
    bronnen.laad("brp", "ruw_brp_stand", kluis)
    # De wijziging van vóór de publicatie komt zonder de kolom; die erna met.
    ruw = tabel(bronnen, "brp", "ruw_brp", "persoon")
    assert set(ruw["indicatie_digitaal_contact"].dropna()) == {"J"}
    stand = tabel(bronnen, "brp", "ruw_brp_stand", "persoon").set_index("id")
    assert stand.loc[2, "indicatie_digitaal_contact"] == "J" and list(stand.index) == [1, 2, 4]
