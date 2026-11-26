"""De bron van het Datafundament: een BRP-database met testpersonen (DF-ADR-010).

De testpersonen komen uit vrijBRP (Procura, EUPL-1.2): de testsets van de RvIG
en GBA-V en de demopersonen van Procura, als persoonslijsten in de structuur
van het LO BRP. Dit script zet ze in PostgreSQL, in een schema dat lijkt op
dat van een BRP-systeem: één tabel per categorie, één kolom per rubriek, met
historie. En het kan de bron laten veranderen, voor de demo van CDC.

    python brp.py schema                 SQL van het schema afdrukken (naar bron/sql/02-schema.sql)
    python brp.py laden                  testpersonen (opnieuw) laden
    python brp.py verhuis [BSN]          een persoon verhuist binnen de gemeente
    python brp.py overlijden [BSN]       een persoon overlijdt
    python brp.py kolom-erbij            nieuwe kolom in brp.persoon (schemawijziging)
    python brp.py status                 aantallen, laatste wijzigingen, replicatie
    python brp.py synthetisch            synthetische bronnen rond de BRP (bag, woz, ...)
    python brp.py melding                nieuwe melding openbare ruimte (demo CDC)
    python brp.py zaak-afhandelen        een open zaak afhandelen (demo CDC)
    python brp.py simuleer [TOT]         de simulatieklok bijwerken tot nu (DF-ADR-014)
    python brp.py simulatie-status       tot waar de klok is, en wat er laatst gebeurde
    python brp.py export-belastingen     nachtelijke export van de belastingen naar de landingsbucket

Zonder BSN kiest het script een geschikte persoon. Verbinding: de PG*-
omgevingsvariabelen (PGHOST, PGUSER, PGPASSWORD, PGDATABASE).
"""

import collections
import io
import json
import os
import random
import re
import sys
import urllib.request
import zipfile
from datetime import date

# Vaste versie van de testdata: een nieuwe versie kies je bewust.
VRIJBRP_COMMIT = "fb9f41badc0191468ad6aa54eb06298cb059eeff"
ZIP_URL = (
    "https://github.com/vrijBRP/vrijBRP-Balie/raw/"
    f"{VRIJBRP_COMMIT}/gba-testdata/src/main/resources/gba-test-people.zip"
)
ZIP_CACHE = os.environ.get("BRP_ZIP", "/data/gba-test-people.zip")

# Tabelnaam per categorie van het LO BRP (30, 32 en 34 zijn eigen categorieën van vrijBRP).
TABELLEN = {
    1: "persoon", 2: "ouder_1", 3: "ouder_2", 4: "nationaliteit", 5: "huwelijk",
    6: "overlijden", 7: "inschrijving", 8: "verblijfplaats", 9: "kind",
    10: "verblijfstitel", 11: "gezag", 12: "reisdocument", 13: "kiesrecht",
    30: "diversen", 32: "woningkaart", 34: "lokale_afnemersindicatie",
}
# Vaste kolommen van elke categorietabel; rubrieken mogen niet zo heten.
VASTE_KOLOMMEN = {"id", "pl_id", "stapel", "volgnr", "actueel", "onjuist", "gewijzigd_op"}
# Elementen die geen code zijn maar een datum, nummer of verwijzing: niet in de codetabel.
GEEN_CODE = re.compile(r"datum|a-nummer|burgerservicenummer|postcode|onderzoek|tijdstempel|aktenummer")
VOORKEUR_SET = ["gbav", "rvig", "demo"]  # bij dubbelen: de vollediger set eerst


# --- Testdata lezen ----------------------------------------------------------

def zip_ophalen():
    if os.path.exists(ZIP_CACHE):
        return ZIP_CACHE
    print(f"Testdata ophalen van vrijBRP-Balie ({VRIJBRP_COMMIT[:7]})")
    os.makedirs(os.path.dirname(ZIP_CACHE), exist_ok=True)
    with urllib.request.urlopen(ZIP_URL, timeout=60) as r:
        inhoud = r.read()
    zipfile.ZipFile(io.BytesIO(inhoud)).testzip()
    with open(ZIP_CACHE, "wb") as f:
        f.write(inhoud)
    return ZIP_CACHE


def kolomnaam(omschrijving):
    naam = re.sub(r"[^a-z0-9]+", "_", omschrijving.lower()
                  .replace("ë", "e").replace("ï", "i").replace("é", "e")).strip("_")
    return naam[:63]


def rubriek(element):
    """1120 → '11.20'"""
    return f"{element // 100:02d}.{element % 100:02d}"


def lees_testdata(pad):
    """Leest de zip. Geeft het model (tabellen en kolommen), de persoonslijsten
    (ontdubbeld op A-nummer) en de codetabel."""
    z = zipfile.ZipFile(pad)
    kolommen = collections.defaultdict(dict)        # categorie → element → kolom
    omschrijvingen = collections.defaultdict(collections.Counter)  # (element, code) → omschrijving
    gevonden = collections.defaultdict(list)        # A-nummer → [(set, persoonslijst)]
    for naam in sorted(z.namelist()):
        if not naam.endswith(".json"):
            continue
        testset = naam.split("/")[0]
        for pl in json.loads(z.read(naam)).get("personlists", []):
            anr = None
            for cat in pl["cats"]:
                for stapel in cat["sets"]:
                    for rec in stapel["records"]:
                        for e in rec["elems"]:
                            kolommen[cat["code"]].setdefault(e["code"], e["descr"])
                            v = e["value"]
                            if v.get("val") and v.get("descr") and v["descr"] != v["val"] \
                                    and not GEEN_CODE.search(e["descr"].lower()):
                                omschrijvingen[(rubriek(e["code"]), v["val"])][v["descr"]] += 1
                            if cat["code"] == 1 and e["code"] == 110 and rec["status"]["code"] == 2:
                                anr = v.get("val")
            if anr:
                gevonden[anr].append((testset, pl))

    model = {}
    for cat, elementen in sorted(kolommen.items()):
        if cat not in TABELLEN:
            raise SystemExit(f"Onbekende categorie {cat} in de testdata; voeg haar toe aan TABELLEN.")
        namen, gezien = {}, set()
        for el, oms in sorted(elementen.items()):
            k = kolomnaam(oms)
            if k in gezien or k in VASTE_KOLOMMEN:
                k = f"{k}_{el}"
            gezien.add(k)
            namen[el] = (k, oms)
        model[cat] = (TABELLEN[cat], namen)

    personen = []
    for anr, lijst in sorted(gevonden.items()):
        lijst.sort(key=lambda t: VOORKEUR_SET.index(t[0]))
        sets = sorted({s for s, _ in lijst}, key=VOORKEUR_SET.index)
        personen.append((anr, sets, lijst[0][1]))

    codes = [(el, code, c.most_common(1)[0][0]) for (el, code), c in sorted(omschrijvingen.items())]
    return model, personen, codes


# --- Schema ------------------------------------------------------------------

def schema_sql(model):
    uit = [
        "-- Schema van de bron: een BRP-database met testpersonen (DF-ADR-010).",
        "-- Gemaakt met: python brp.py schema  (niet met de hand wijzigen)",
        f"-- Testdata: vrijBRP-Balie {VRIJBRP_COMMIT[:7]}, gba-test-people.zip (EUPL-1.2)",
        "",
        "CREATE SCHEMA brp;",
        "",
        "-- Eén rij per persoon. testsets: in welke testset(s) van vrijBRP de persoon voorkomt.",
        "CREATE TABLE brp.persoonslijst (",
        "  id bigserial PRIMARY KEY,",
        "  a_nummer text NOT NULL UNIQUE,",
        "  burgerservicenummer text,",
        "  testsets text[] NOT NULL,",
        "  gewijzigd_op timestamptz NOT NULL DEFAULT now()",
        ");",
        "",
        "-- Codes met hun omschrijving, zoals de testdata ze levert (vergelijkbaar met de",
        "-- landelijke tabellen). element: groep en element van het LO BRP, bijvoorbeeld 09.10.",
        "CREATE TABLE brp.codetabel (",
        "  element text NOT NULL,",
        "  code text NOT NULL,",
        "  omschrijving text NOT NULL,",
        "  PRIMARY KEY (element, code)",
        ");",
    ]
    for cat, (tabel, namen) in sorted(model.items()):
        uit += [
            "",
            f"-- Categorie {cat:02d}: {tabel}. Per stapel de records; actueel = de actuele stand,",
            "-- de andere rijen zijn historie. volgnr: de volgorde in de bron.",
            f"CREATE TABLE brp.{tabel} (",
            "  id bigserial PRIMARY KEY,",
            "  pl_id bigint NOT NULL REFERENCES brp.persoonslijst (id),",
            "  stapel integer NOT NULL,",
            "  volgnr integer NOT NULL,",
            "  actueel boolean NOT NULL,",
            "  onjuist boolean NOT NULL DEFAULT false,",
            "  gewijzigd_op timestamptz NOT NULL DEFAULT now(),",
        ]
        uit += [f"  {k} text," for k, _ in namen.values()]
        uit += ["  UNIQUE (pl_id, stapel, volgnr)", ");",
                f"CREATE INDEX ON brp.{tabel} (pl_id) WHERE actueel;"]
        for el, (k, oms) in namen.items():
            oms_sql = oms.replace("'", "''")
            uit.append(f"COMMENT ON COLUMN brp.{tabel}.{k} IS '{cat:02d}.{rubriek(el)} {oms_sql}';")
    return "\n".join(uit) + "\n"


# --- Database ----------------------------------------------------------------

def verbind():
    import psycopg  # pylint: disable=import-outside-toplevel
    return psycopg.connect(autocommit=False)


def laden():
    from psycopg import sql  # pylint: disable=import-outside-toplevel
    model, personen, codes = lees_testdata(zip_ophalen())
    with verbind() as con, con.cursor() as cur:
        # Klopt het schema in de database met de testdata?
        for cat, (tabel, namen) in model.items():
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'brp' AND table_name = %s", (tabel,))
            bestaand = {r[0] for r in cur.fetchall()}
            mist = [k for k, _ in namen.values() if k not in bestaand]
            if mist:
                raise SystemExit(f"Tabel brp.{tabel} mist kolommen {mist}. Is sql/02-schema.sql bijgewerkt?")
        tabellen = ["persoonslijst", "codetabel"] + [t for t, _ in model.values()]
        cur.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
            sql.SQL(", ").join(sql.Identifier("brp", t) for t in tabellen)))
        cur.executemany("INSERT INTO brp.codetabel (element, code, omschrijving) VALUES (%s, %s, %s)", codes)

        aantal = collections.Counter()
        for anr, sets, pl in personen:
            bsn = None
            for cat in pl["cats"]:
                if cat["code"] == 1:
                    for s in cat["sets"]:
                        for r in s["records"]:
                            if r["status"]["code"] == 2:
                                bsn = next((e["value"]["val"] for e in r["elems"] if e["code"] == 120), bsn)
            cur.execute("INSERT INTO brp.persoonslijst (a_nummer, burgerservicenummer, testsets) "
                        "VALUES (%s, %s, %s) RETURNING id", (anr, bsn, sets))
            pl_id = cur.fetchone()[0]
            for cat in pl["cats"]:
                tabel, namen = model[cat["code"]]
                for s in cat["sets"]:
                    for r in s["records"]:
                        waarden = {namen[e["code"]][0]: e["value"].get("val") for e in r["elems"]}
                        k = list(waarden)
                        cur.execute(
                            sql.SQL("INSERT INTO {} (pl_id, stapel, volgnr, actueel, onjuist, {}) "
                                    "VALUES (%s, %s, %s, %s, %s, {})").format(
                                sql.Identifier("brp", tabel),
                                sql.SQL(", ").join(map(sql.Identifier, k)),
                                sql.SQL(", ").join(sql.Placeholder() * len(k))),
                            [pl_id, s["index"], r["index"], r["status"]["code"] == 2,
                             bool(r["incorrect"])] + [waarden[x] for x in k])
                        aantal[tabel] += 1
        con.commit()
    print(f"Geladen: {len(personen)} persoonslijsten, {len(codes)} codes.")
    for tabel, n in sorted(aantal.items()):
        print(f"  brp.{tabel:26} {n:6} rijen")


def kies_persoon(cur, bsn, voorwaarde, uitleg):
    """Een persoon met BSN, of een willekeurige die aan de voorwaarde voldoet."""
    if bsn:
        cur.execute(f"SELECT pl.id FROM brp.persoonslijst pl WHERE pl.burgerservicenummer = %s AND {voorwaarde}",
                    (bsn.zfill(9),))
    else:
        cur.execute(f"SELECT pl.id FROM brp.persoonslijst pl WHERE {voorwaarde} ORDER BY random() LIMIT 1")
    rij = cur.fetchone()
    if not rij:
        raise SystemExit(f"Geen persoon gevonden{' met BSN ' + bsn if bsn else ''} {uitleg}.")
    return rij[0]


def naam_van(cur, pl_id):
    cur.execute("SELECT concat_ws(' ', voornamen, voorvoegsel_geslachtsnaam, geslachtsnaam), burgerservicenummer "
                "FROM brp.persoon WHERE pl_id = %s AND actueel LIMIT 1", (pl_id,))
    return cur.fetchone() or ("?", "?")


def vandaag():
    return date.today().strftime("%Y%m%d")


def verhuis(bsn=None):
    """Verhuizing binnen de gemeente: het actuele adres wordt historie, het nieuwe
    adres (van een andere persoon in dezelfde gemeente) wordt actueel."""
    with verbind() as con, con.cursor() as cur:
        pl_id = kies_persoon(cur, bsn,
                             "EXISTS (SELECT 1 FROM brp.verblijfplaats v WHERE v.pl_id = pl.id AND v.actueel "
                             "AND v.postcode <> '' AND v.huisnummer <> '' AND coalesce(v.land_waarnaar_vertrokken, '') = '') "
                             "AND NOT EXISTS (SELECT 1 FROM brp.overlijden o WHERE o.pl_id = pl.id AND o.actueel)",
                             "die in Nederland woont en leeft")
        cur.execute("SELECT * FROM brp.verblijfplaats WHERE pl_id = %s AND actueel", (pl_id,))
        kolommen = [d.name for d in cur.description]
        oud = dict(zip(kolommen, cur.fetchone()))
        cur.execute("SELECT * FROM brp.verblijfplaats WHERE actueel AND gemeente_van_inschrijving = %s "
                    "AND postcode <> '' AND (postcode, huisnummer) <> (%s, %s) ORDER BY random() LIMIT 1",
                    (oud["gemeente_van_inschrijving"], oud["postcode"], oud["huisnummer"]))
        donor = cur.fetchone()
        if not donor:
            raise SystemExit("Geen ander adres in dezelfde gemeente gevonden.")
        donor = dict(zip(kolommen, donor))
        adres = [k for k in kolommen if k.startswith(("straatnaam", "openbare_ruimte", "huisnummer", "huisletter",
                                                     "aanduiding_bij", "postcode", "woonplaatsnaam",
                                                     "identificatie", "gemeentedeel", "locatiebeschrijving"))]
        nieuw = {k: oud[k] for k in kolommen if k not in ("id", "gewijzigd_op")}
        nieuw.update({k: donor[k] for k in adres})
        nieuw.update(actueel=True, onjuist=False, functie_adres="W",
                     datum_aanvang_adreshouding=vandaag(), ingangsdatum_geldigheid=vandaag(),
                     datum_van_opneming=vandaag(), omschrijving_van_de_aangifte_adreshouding="I")
        cur.execute("SELECT max(volgnr) + 1 FROM brp.verblijfplaats WHERE pl_id = %s AND stapel = %s",
                    (pl_id, oud["stapel"]))
        nieuw["volgnr"] = cur.fetchone()[0]
        cur.execute("UPDATE brp.verblijfplaats SET actueel = false, gewijzigd_op = now() WHERE id = %s", (oud["id"],))
        k = list(nieuw)
        cur.execute(f"INSERT INTO brp.verblijfplaats ({', '.join(k)}) VALUES ({', '.join(['%s'] * len(k))})",
                    [nieuw[x] for x in k])
        cur.execute("UPDATE brp.persoonslijst SET gewijzigd_op = now() WHERE id = %s", (pl_id,))
        naam, bsn = naam_van(cur, pl_id)
        con.commit()
    print(f"Verhuisd: {naam} (BSN {bsn})")
    print(f"  van {oud['straatnaam']} {oud['huisnummer']}, {oud['postcode']} {oud['woonplaatsnaam']}")
    print(f"  naar {donor['straatnaam']} {donor['huisnummer']}, {donor['postcode']} {donor['woonplaatsnaam']}")


def overlijden(bsn=None):
    """Overlijden: een record in categorie 06, en de bijhouding wordt opgeschort (07)."""
    with verbind() as con, con.cursor() as cur:
        pl_id = kies_persoon(cur, bsn,
                             "NOT EXISTS (SELECT 1 FROM brp.overlijden o WHERE o.pl_id = pl.id) "
                             "AND EXISTS (SELECT 1 FROM brp.verblijfplaats v WHERE v.pl_id = pl.id AND v.actueel "
                             "AND v.postcode <> '')",
                             "die in Nederland woont en nog niet is overleden")
        cur.execute("SELECT gemeente_van_inschrijving FROM brp.verblijfplaats WHERE pl_id = %s AND actueel", (pl_id,))
        gemeente = cur.fetchone()[0]
        cur.execute("INSERT INTO brp.overlijden (pl_id, stapel, volgnr, actueel, datum_overlijden, plaats_overlijden, "
                    "land_overlijden, ingangsdatum_geldigheid, datum_van_opneming) "
                    "VALUES (%s, 1, 1, true, %s, %s, '6030', %s, %s)",
                    (pl_id, vandaag(), gemeente, vandaag(), vandaag()))
        cur.execute("UPDATE brp.inschrijving SET datum_opschorting_bijhouding = %s, "
                    "omschrijving_reden_opschorting_bijhouding = 'O', gewijzigd_op = now() "
                    "WHERE pl_id = %s AND actueel", (vandaag(), pl_id))
        cur.execute("UPDATE brp.persoonslijst SET gewijzigd_op = now() WHERE id = %s", (pl_id,))
        naam, bsn = naam_van(cur, pl_id)
        con.commit()
    print(f"Overleden: {naam} (BSN {bsn}), vandaag, in gemeente {gemeente}")


def kolom_erbij():
    """Schemawijziging in de bron: een nieuwe kolom, met een waarde bij een paar personen."""
    with verbind() as con, con.cursor() as cur:
        cur.execute("ALTER TABLE brp.persoon ADD COLUMN IF NOT EXISTS indicatie_digitaal_contact text")
        cur.execute("COMMENT ON COLUMN brp.persoon.indicatie_digitaal_contact IS "
                    "'Nieuw in de bron (demo schemawijziging): J als de persoon digitaal contact wil'")
        cur.execute("UPDATE brp.persoon SET indicatie_digitaal_contact = 'J', gewijzigd_op = now() "
                    "WHERE actueel AND id IN (SELECT id FROM brp.persoon WHERE actueel ORDER BY random() LIMIT 25)")
        n = cur.rowcount
        con.commit()
    print(f"Kolom brp.persoon.indicatie_digitaal_contact toegevoegd; {n} personen hebben 'J'.")


def status():
    with verbind() as con, con.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'brp' ORDER BY 1")
        print("Tabellen:")
        for (t,) in cur.fetchall():
            cur.execute(f'SELECT count(*), count(*) FILTER (WHERE gewijzigd_op > now() - interval \'1 day\') '
                        f'FROM brp."{t}"' if t != "codetabel" else 'SELECT count(*), 0 FROM brp.codetabel')
            n, recent = cur.fetchone()
            print(f"  brp.{t:26} {n:6} rijen{f', {recent} gewijzigd in het laatste etmaal' if recent else ''}")
        cur.execute("SELECT pubname FROM pg_publication")
        print("Publicaties:", ", ".join(r[0] for r in cur.fetchall()) or "geen")
        cur.execute("SELECT slot_name, active, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) "
                    "FROM pg_replication_slots")
        slots = cur.fetchall()
        print("Replicatieslots:", "geen" if not slots else "")
        for naam, actief, achter in slots:
            print(f"  {naam}: {'actief' if actief else 'niet actief'}, {achter} WAL vastgehouden")


def main(args):
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    opdracht, rest = args[0], args[1:]
    if opdracht == "schema":
        model, personen, codes = lees_testdata(zip_ophalen())
        sys.stdout.write(schema_sql(model))
        print(f"-- {len(personen)} persoonslijsten, {len(codes)} codes in de testdata", file=sys.stderr)
    elif opdracht == "laden":
        laden()
    elif opdracht == "verhuis":
        verhuis(rest[0] if rest else None)
    elif opdracht == "overlijden":
        overlijden(rest[0] if rest else None)
    elif opdracht == "kolom-erbij":
        kolom_erbij()
    elif opdracht == "status":
        status()
    elif opdracht in ("simuleer", "simulatie-status"):
        import simulatie  # pylint: disable=import-outside-toplevel
        with verbind() as con:
            if opdracht == "simuleer":
                simulatie.simuleer(con, args[1] if len(args) > 1 else None)
            else:
                simulatie.status(con)
    elif opdracht == "export-belastingen":
        import export  # pylint: disable=import-outside-toplevel
        with verbind() as con:
            export.belastingen(con)
    elif opdracht in ("synthetisch", "melding", "zaak-afhandelen"):
        import synthetisch  # pylint: disable=import-outside-toplevel
        actie = {"synthetisch": synthetisch.synthetisch, "melding": synthetisch.melding,
                 "zaak-afhandelen": synthetisch.zaak_afhandelen}[opdracht]
        with verbind() as con:
            actie(con)
    else:
        raise SystemExit(f"Onbekende opdracht: {opdracht}. Zie: python brp.py help")


if __name__ == "__main__":
    random.seed()
    main(sys.argv[1:])
