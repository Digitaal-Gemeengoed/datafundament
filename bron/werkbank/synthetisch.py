"""Synthetische gemeentelijke bronnen rond de BRP-testdata (DF-ADR-010).

Wat een gemeente in haar datawarehouse aantreft, verzonnen maar samenhangend:

  bag          woonplaatsen, openbare ruimten, nummeraanduidingen, panden en
               verblijfsobjecten; precies passend op de adressen in de BRP, met
               de BAG-identificaties die de BRP al noemt, plus niet-woonobjecten
               en leegstand. Met een paar bewuste BAG-BRP-verschillen.
  woz          WOZ-objecten per verblijfsobject, waarde per peildatum, eigenaar
               en gebruiker (BSN van bewoners, of een woningcorporatie).
  belastingen  aanslagen OZB (eigenaren) en afvalstoffenheffing (per huishouden).
  mor          meldingen openbare ruimte met statusverloop (zoals Signalen).
  zaken        zaken met zaaktype, initiator, BAG-object en statusverloop.
  sociaal      Wmo-voorzieningen, jeugdhulp, Participatiewet (art. 9 AVG).

Alles volgt uit de BRP en een vaste seed: dezelfde BRP geeft dezelfde data.
Coördinaten zijn verzonnen (RD, rond een middelpunt per gemeente); voor echte
locaties is er de Locatieserver (ingestie/pdok.py).

    python brp.py synthetisch          alles opnieuw maken (na brp.py laden)
    python brp.py melding              een nieuwe melding (demo CDC)
    python brp.py zaak-afhandelen      een open zaak afhandelen (demo CDC)
"""

import collections
import math
import os
import random
from datetime import date, datetime, timedelta, timezone

SEED = 20261126
PEILDATUM = date(2026, 11, 26)  # "vandaag" voor leeftijden en datums; vast voor herhaalbaarheid
SCHEMAS = ["bag", "woz", "belastingen", "mor", "zaken", "sociaal"]
# Wat dfc rechtstreeks uit de database mag lezen (CDC). Zaken komen via de Zaken-API
# en belastingen via een nachtelijke export (DF-ADR-014), zoals bij echte leveranciers.
CDC_SCHEMAS = ["bag", "woz", "mor", "sociaal"]
INWONERS = 1500  # extra synthetische huishoudens in de BRP
SQL_BESTAND = os.path.join(os.path.dirname(__file__), "synthetisch.sql")

# Een middelpunt in RD per gemeente (ongeveer het centrum); andere gemeenten
# krijgen een vast, verzonnen punt binnen Nederland.
MIDDELPUNT = {"0518": (81000, 455000), "0599": (92500, 437500), "0363": (121500, 487000),
              "1904": (128000, 463000), "0344": (136500, 456000), "0014": (234000, 582000)}
M2_PRIJS = {"0363": 7200, "0518": 4300, "0599": 3900, "0344": 4800}  # euro per m2, woningen (verzonnen)

NIET_WOON = ["winkelfunctie", "kantoorfunctie", "bijeenkomstfunctie", "gezondheidszorgfunctie",
             "industriefunctie", "onderwijsfunctie", "logiesfunctie", "sportfunctie"]
SOORT_WOZ = {"woonfunctie": "woning", "winkelfunctie": "winkel", "kantoorfunctie": "kantoor",
             "industriefunctie": "bedrijfsruimte", "logiesfunctie": "hotel"}
CORPORATIES = [("NNP-00000001", "Woonstichting Testwijk"), ("NNP-00000002", "Stichting Huisvesting Voorbeeld"),
               ("NNP-00000003", "Wooncorporatie De Proef")]
BEDRIJVEN = [("NNP-%08d" % i, n) for i, n in enumerate(
    ["Bakkerij De Voorbeeldhoek", "Kantoorbeheer Proefstad", "Sportschool Testfit", "Huisartsenpraktijk Demo",
     "Basisschool De Testbank", "Hotel Steekproef", "Garagebedrijf Fictief", "Café Het Model"], start=11)]
ZAAKTYPEN = [("ZT-WMO", "Wmo-aanvraag", 56), ("ZT-OMV", "Omgevingsvergunning", 56),
             ("ZT-PARK", "Parkeervergunning bewoner", 14), ("ZT-VERH", "Verhuizing doorgeven", 5),
             ("ZT-UITT", "Uittreksel BRP", 2), ("ZT-EVEN", "Melding klein evenement", 28),
             ("ZT-KWIJT", "Kwijtschelding gemeentelijke belastingen", 56)]
MOR_CATEGORIEN = [("Afval", "Grofvuil", 3), ("Afval", "Container vol", 2), ("Afval", "Zwerfafval", 5),
                  ("Wegen, verkeer, straatmeubilair", "Losse stoeptegel", 14),
                  ("Wegen, verkeer, straatmeubilair", "Gat in de weg", 10),
                  ("Openbaar groen en water", "Boom", 21), ("Openbaar groen en water", "Onkruid", 14),
                  ("Verlichting", "Lantaarnpaal kapot", 7), ("Overlast van en door personen of groepen", "Jongeren", 2),
                  ("Overlast bedrijven en horeca", "Geluid", 3), ("Wegen, verkeer, straatmeubilair", "Fietswrak", 21)]
WMO = [("hulp bij het huishouden", 0.45), ("individuele begeleiding", 0.2), ("woningaanpassing", 0.1),
       ("scootmobiel", 0.1), ("Wmo-vervoer", 0.15)]
JEUGD = [("ambulant", 0.75), ("verblijf", 0.15), ("jeugdbescherming", 0.10)]
JEUGD_AANBIEDERS = ["Jeugdhulp Testregio", "Stichting Ambulant Voorbeeld", "Gezinshuis De Proef", "Jeugdbescherming Demo"]


def _dt(d, uur=10):
    return datetime(d.year, d.month, d.day, uur, 0, tzinfo=timezone.utc)


def _datum(s):
    """BRP-datum JJJJMMDD → date, of None."""
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8])) if s and len(s) == 8 and s[4:] != "0000" else None
    except ValueError:
        return None


def _leeftijd(geb):
    if not geb:
        return None
    return PEILDATUM.year - geb.year - ((PEILDATUM.month, PEILDATUM.day) < (geb.month, geb.day))


def _bag_id(waarde, typecode):
    """Een BAG-identificatie uit de BRP gebruiken als die geldig is (16 cijfers, juiste typecode)."""
    return waarde if waarde and len(waarde) == 16 and waarde.isdigit() and waarde[4:6] == typecode else None


def _kies(rng, gewogen):
    return rng.choices([w for w, _ in gewogen], weights=[g for _, g in gewogen])[0]


# --- BRP lezen -------------------------------------------------------------------------

def lees_brp(cur, schema="brp"):
    """Personen en verblijfplaatsen uit de BRP (werkt met PostgreSQL en, voor tests, DuckDB)."""
    def rijen(sql):
        cur.execute(sql)
        namen = [d[0] for d in cur.description]
        return [dict(zip(namen, r)) for r in cur.fetchall()]

    personen = rijen(f"""
        SELECT p.pl_id, pl.burgerservicenummer AS bsn, p.geboortedatum,
               EXISTS (SELECT 1 FROM {schema}.overlijden o WHERE o.pl_id = p.pl_id AND o.actueel) AS overleden
        FROM {schema}.persoon p JOIN {schema}.persoonslijst pl ON pl.id = p.pl_id
        WHERE p.actueel ORDER BY p.pl_id""")
    verblijf = rijen(f"""
        SELECT pl_id, actueel, gemeente_van_inschrijving AS gemeente, straatnaam, huisnummer, huisletter,
               huisnummertoevoeging AS toevoeging, postcode, woonplaatsnaam,
               identificatie_verblijfplaats AS vbo_brp, identificatiecode_nummeraanduiding AS num_brp,
               datum_aanvang_adreshouding
        FROM {schema}.verblijfplaats ORDER BY pl_id, actueel, volgnr""")
    gemeenten = {r["code"]: r["omschrijving"] for r in rijen(
        f"SELECT code, omschrijving FROM {schema}.codetabel WHERE element = '09.10'")}
    return personen, verblijf, gemeenten


# --- Genereren -----------------------------------------------------------------------------

def genereer(personen, verblijf, gemeenten, seed=SEED):
    """Geeft {schema: {tabel: [rijen]}} en een verslag (wat er bewust afwijkt)."""
    rng = random.Random(seed)
    uit = {s: collections.defaultdict(list) for s in SCHEMAS}
    verslag = collections.Counter()

    pers = {}
    for p in personen:
        if p["bsn"]:
            pers[p["pl_id"]] = dict(bsn=p["bsn"], geb=_datum(p["geboortedatum"]), overleden=bool(p["overleden"]))

    # 1. Adressen uit de BRP (actueel en historie), ontdubbeld.
    adressen, bewoners = {}, collections.defaultdict(list)
    for v in verblijf:
        if not (v["postcode"] and v["huisnummer"] and v["gemeente"] and v["huisnummer"].isdigit()):
            continue
        k = (v["gemeente"], v["postcode"], int(v["huisnummer"]), v["huisletter"] or None, v["toevoeging"] or None)
        if k not in adressen:
            adressen[k] = dict(straat=v["straatnaam"] or "Onbekende straat", woonplaats=v["woonplaatsnaam"],
                               num_brp=v["num_brp"], vbo_brp=v["vbo_brp"])
        if v["actueel"] and v["pl_id"] in pers and not pers[v["pl_id"]]["overleden"]:
            bewoners[k].append(dict(pl_id=v["pl_id"], **pers[v["pl_id"]],
                                    sinds=_datum(v["datum_aanvang_adreshouding"])))

    # 2. BAG: woonplaatsen, straten, panden, nummeraanduidingen, verblijfsobjecten.
    volg = collections.Counter()

    def nieuw_id(gemeente, typecode):
        volg[(gemeente, typecode)] += 1
        return f"{gemeente}{typecode}{9000000000 + volg[(gemeente, typecode)]:010d}"

    woonplaatsen, straten, panden = {}, {}, {}
    gebruikt = set()
    vbo_info = {}  # vbo-id -> dict (voor WOZ, meldingen, zaken)
    centrum = {}

    def middelpunt(gemeente):
        if gemeente not in centrum:
            r = random.Random(f"{seed}-{gemeente}")
            centrum[gemeente] = MIDDELPUNT.get(gemeente, (r.randint(60000, 230000), r.randint(360000, 580000)))
        return centrum[gemeente]

    def woonplaats(gemeente, naam):
        if not naam or naam.isdigit():
            naam = gemeenten.get(gemeente, f"Gemeente {gemeente}")
        k = (gemeente, naam)
        if k not in woonplaatsen:
            wid = f"{9000 + len(woonplaatsen) + 1}"
            woonplaatsen[k] = wid
            uit["bag"]["woonplaats"].append(dict(identificatie=wid, naam=naam, gemeentecode=gemeente,
                                                 status="Woonplaats aangewezen"))
        return woonplaatsen[k]

    def straat(gemeente, wid, naam):
        k = (wid, naam)
        if k not in straten:
            cx, cy = middelpunt(gemeente)
            hoek = rng.uniform(0, math.pi)
            straten[k] = dict(id=nieuw_id(gemeente, "30"), x=cx + rng.uniform(-2500, 2500),
                              y=cy + rng.uniform(-2500, 2500), dx=math.cos(hoek), dy=math.sin(hoek),
                              max_nr=0, postcode=None, gemeente=gemeente)
            uit["bag"]["openbare_ruimte"].append(dict(identificatie=straten[k]["id"], naam=naam, type="Weg",
                                                      woonplaats_identificatie=wid, status="Naamgeving uitgegeven"))
        return straten[k]

    def punt(s, nr):
        zijde = 12 if nr % 2 else -12
        return (round(s["x"] + s["dx"] * nr * 6 - s["dy"] * zijde, 1), round(s["y"] + s["dy"] * nr * 6 + s["dx"] * zijde, 1))

    def pand(s, nr, gemeente):
        k = (s["id"], nr)
        if k not in panden:
            x, y = punt(s, nr)
            bouwjaar = _kies(rng, [(rng.randint(1880, 1919), 1), (rng.randint(1920, 1944), 1.2), (rng.randint(1945, 1969), 2),
                                   (rng.randint(1970, 1989), 2), (rng.randint(1990, 2009), 1.6), (rng.randint(2010, 2025), 1)])
            panden[k] = nieuw_id(gemeente, "10")
            uit["bag"]["pand"].append(dict(
                identificatie=panden[k], oorspronkelijk_bouwjaar=bouwjaar, status="Pand in gebruik",
                geometrie_wkt=f"POLYGON(({x-5} {y-6},{x+5} {y-6},{x+5} {y+6},{x-5} {y+6},{x-5} {y-6}))"))
            panden[k + ("bouwjaar",)] = bouwjaar
        return panden[k], panden[k + ("bouwjaar",)]

    def verblijfsobject(gemeente, s, nr, letter, toev, postcode, gebruiksdoel, vbo_id=None, num_id=None,
                        status="Verblijfsobject in gebruik"):
        num_id = num_id or nieuw_id(gemeente, "20")
        vbo_id = vbo_id or nieuw_id(gemeente, "01")
        pid, bouwjaar = pand(s, nr, gemeente)
        x, y = punt(s, nr)
        appartement = bool(letter or toev)
        opp = rng.randint(40, 110) if appartement else rng.randint(70, 190)
        if gebruiksdoel != "woonfunctie":
            opp = rng.randint(60, 900)
        uit["bag"]["nummeraanduiding"].append(dict(
            identificatie=num_id, huisnummer=nr, huisletter=letter, huisnummertoevoeging=toev, postcode=postcode,
            type_adresseerbaar_object="Verblijfsobject", openbare_ruimte_identificatie=s["id"],
            status="Naamgeving uitgegeven"))
        uit["bag"]["verblijfsobject"].append(dict(
            identificatie=vbo_id, hoofdadres_identificatie=num_id, pand_identificatie=pid, gebruiksdoel=gebruiksdoel,
            oppervlakte=opp, status=status, geometrie_wkt=f"POINT({x} {y})"))
        vbo_info[vbo_id] = dict(gemeente=gemeente, num=num_id, pand=pid, doel=gebruiksdoel, opp=opp,
                                bouwjaar=bouwjaar, x=x, y=y, status=status, bewoners=[])
        s["max_nr"] = max(s["max_nr"], nr)
        s["postcode"] = s["postcode"] or postcode
        return vbo_id

    for k in sorted(adressen, key=lambda k: (k[0], k[1], k[2], k[3] or "", k[4] or "")):
        gemeente, postcode, nr, letter, toev = k
        a = adressen[k]
        afwijking = rng.random()
        if afwijking < 0.015:            # bewust: adres uit de BRP staat niet in de BAG
            verslag["BRP-adres ontbreekt in de BAG"] += 1
            continue
        s = straat(gemeente, woonplaats(gemeente, a["woonplaats"]), a["straat"])
        num_id, vbo_id = _bag_id(a["num_brp"], "20"), _bag_id(a["vbo_brp"], "01")
        if num_id in gebruikt:
            num_id = None
        if vbo_id in gebruikt:
            vbo_id = None
        if (a["num_brp"] or a["vbo_brp"]) and not (num_id and vbo_id):
            verslag["BRP noemt een ongeldige of dubbele BAG-identificatie"] += 1
        bag_postcode, status = postcode, "Verblijfsobject in gebruik"
        if 0.015 <= afwijking < 0.03:    # bewust: andere postcode in de BAG
            bag_postcode = postcode[:5] + ("A" if postcode[5] != "A" else "B")
            verslag["Postcode in de BAG wijkt af van de BRP"] += 1
        elif 0.03 <= afwijking < 0.06 and bewoners.get(k):  # bewust: bewoond, maar ingetrokken in de BAG
            status = "Verblijfsobject ingetrokken"
            verslag["Bewoond verblijfsobject is ingetrokken in de BAG"] += 1
        vid = verblijfsobject(gemeente, s, nr, letter, toev, bag_postcode, "woonfunctie", vbo_id, num_id, status)
        gebruikt.update({vbo_info[vid]["num"], vid})
        vbo_info[vid]["bewoners"] = bewoners.get(k, [])

    # Niet-woonobjecten en leegstaande woningen langs dezelfde straten.
    for s in list(straten.values()):
        if rng.random() < 0.35:
            for _ in range(rng.randint(1, 2)):
                verblijfsobject(s["gemeente"], s, s["max_nr"] + 2, None, None, s["postcode"],
                                rng.choice(NIET_WOON))
        if rng.random() < 0.15:
            verblijfsobject(s["gemeente"], s, s["max_nr"] + 2, None, None, s["postcode"], "woonfunctie")
            verslag["Leegstaande woning (geen bewoners in de BRP)"] += 1

    # 3. WOZ: object, waarde per peildatum, belanghebbenden.
    woz_van_vbo = {}
    for i, (vid, v) in enumerate(sorted(vbo_info.items()), start=1):
        if v["status"] != "Verblijfsobject in gebruik":
            continue
        wnr = f"{v['gemeente']}{i:08d}"
        woz_van_vbo[vid] = wnr
        uit["woz"]["object"].append(dict(wozobjectnummer=wnr, verblijfsobject_identificatie=vid,
                                         soort_object=SOORT_WOZ.get(v["doel"], "overig"), gemeentecode=v["gemeente"]))
        factor = 1.15 if v["bouwjaar"] >= 2000 else 0.95 if v["bouwjaar"] < 1945 else 1.0
        prijs = M2_PRIJS.get(v["gemeente"], 3400) * (1 if v["doel"] == "woonfunctie" else 0.55)
        waarde = v["opp"] * prijs * factor * rng.uniform(0.85, 1.15)
        v["woz"] = {}
        for jaar, groei in [(2021, 0), (2022, 0.13), (2023, 0.05), (2024, 0.03), (2025, 0.08)]:
            waarde *= 1 + groei + rng.uniform(-0.02, 0.02)
            v["woz"][jaar] = int(round(waarde, -3))
            uit["woz"]["waarde"].append(dict(wozobjectnummer=wnr, waardepeildatum=date(jaar, 1, 1),
                                             vastgestelde_waarde=v["woz"][jaar]))
        volwassen = sorted([b for b in v["bewoners"] if (_leeftijd(b["geb"]) or 0) >= 18],
                           key=lambda b: b["geb"] or PEILDATUM)
        if v["doel"] == "woonfunctie" and volwassen and rng.random() < 0.6:
            v["eigenaar"] = ("bsn", volwassen[0]["bsn"], None)
        elif v["doel"] == "woonfunctie":
            v["eigenaar"] = ("nnp",) + rng.choice(CORPORATIES)
        else:
            v["eigenaar"] = ("nnp",) + rng.choice(BEDRIJVEN)
        v["gebruiker"] = ("bsn", volwassen[0]["bsn"], None) if volwassen else (
            v["eigenaar"] if v["doel"] != "woonfunctie" else None)
        sinds = min((b["sinds"] for b in volwassen if b["sinds"]), default=None) or date(2012, 1, 1)
        for rol, wie in [("eigenaar", v["eigenaar"]), ("gebruiker", v["gebruiker"])]:
            if wie:
                uit["woz"]["belanghebbende"].append(dict(
                    wozobjectnummer=wnr, rol=rol, bsn=wie[1] if wie[0] == "bsn" else None,
                    nnp_id=wie[1] if wie[0] == "nnp" else None, nnp_naam=wie[2] if wie[0] == "nnp" else None,
                    begindatum=sinds if wie[0] == "bsn" else date(2005, 1, 1), einddatum=None))

    # 4. Sociaal domein, op leeftijd; daarna zaken die erbij horen.
    zaken_teller = collections.Counter()

    def zaak(type_id, registratie, eind, initiator_bsn=None, nnp=None, obj=None, resultaat=None):
        zaken_teller[registratie.year] += 1
        zid = f"ZAAK-{registratie.year}-{zaken_teller[registratie.year]:06d}"
        uit["zaken"]["zaak"].append(dict(identificatie=zid, zaaktype_identificatie=type_id, initiator_bsn=initiator_bsn,
                                         initiator_nnp_id=nnp, object_identificatie=obj, registratiedatum=registratie,
                                         einddatum=eind, resultaat=resultaat))
        uit["zaken"]["status"].append(dict(zaak_identificatie=zid, statustype="Ontvangen",
                                           datum_status_gezet=_dt(registratie, 9)))
        behandeling = registratie + timedelta(days=rng.randint(1, 5))
        if behandeling <= PEILDATUM and (eind is None or behandeling <= eind):
            uit["zaken"]["status"].append(dict(zaak_identificatie=zid, statustype="In behandeling",
                                               datum_status_gezet=_dt(behandeling, 11)))
        if eind:
            uit["zaken"]["status"].append(dict(zaak_identificatie=zid, statustype="Afgehandeld",
                                               datum_status_gezet=_dt(eind, 15)))
        return zid

    for zt, oms, termijn in ZAAKTYPEN:
        uit["zaken"]["zaaktype"].append(dict(identificatie=zt, omschrijving=oms, doorlooptijd_dagen=termijn))

    adres_van = {b["pl_id"]: vid for vid, v in vbo_info.items() for b in v["bewoners"]}
    bijstand = set()
    for p in sorted(pers.items()):
        pl_id, info = p
        if info["overleden"] or pl_id not in adres_van:
            continue
        lft = _leeftijd(info["geb"])
        if lft is None:
            continue
        vid = adres_van[pl_id]
        kans_wmo = 0.25 if lft >= 75 else 0.10 if lft >= 65 else 0.03 if lft >= 18 else 0
        if rng.random() < kans_wmo:
            start = PEILDATUM - timedelta(days=rng.randint(30, 6 * 365))
            aanvraag = start - timedelta(days=rng.randint(20, 70))
            zid = zaak("ZT-WMO", aanvraag, start - timedelta(days=rng.randint(0, 10)), info["bsn"], obj=vid,
                       resultaat="toegekend")
            eind = start + timedelta(days=rng.randint(180, 1500)) if rng.random() < 0.4 else None
            uit["sociaal"]["wmo_voorziening"].append(dict(
                bsn=info["bsn"], voorziening=_kies(rng, WMO), leveringsvorm="PGB" if rng.random() < 0.15 else "ZIN",
                startdatum=start, einddatum=eind if eind and eind < PEILDATUM else None, zaak_identificatie=zid))
        elif lft >= 65 and rng.random() < 0.08:   # lopende aanvraag, nog niet besloten
            zaak("ZT-WMO", PEILDATUM - timedelta(days=rng.randint(3, 50)), None, info["bsn"], obj=vid)
        elif lft >= 18 and rng.random() < 0.02:
            aanvraag = PEILDATUM - timedelta(days=rng.randint(30, 3 * 365))
            zaak("ZT-WMO", aanvraag, aanvraag + timedelta(days=rng.randint(20, 70)), info["bsn"], obj=vid,
                 resultaat="afgewezen")
        if lft < 18 and rng.random() < 0.30:
            start = PEILDATUM - timedelta(days=rng.randint(30, 4 * 365))
            eind = start + timedelta(days=rng.randint(90, 900)) if rng.random() < 0.5 else None
            uit["sociaal"]["jeugdhulp_traject"].append(dict(
                bsn=info["bsn"], soort=_kies(rng, JEUGD), aanbieder=rng.choice(JEUGD_AANBIEDERS),
                startdatum=start, einddatum=eind if eind and eind < PEILDATUM else None))
        if 21 <= lft <= 66 and rng.random() < 0.06:
            start = PEILDATUM - timedelta(days=rng.randint(60, 6 * 365))
            eind = start + timedelta(days=rng.randint(120, 1500)) if rng.random() < 0.35 else None
            eind = eind if eind and eind < PEILDATUM else None
            if eind is None:
                bijstand.add(info["bsn"])
            uit["sociaal"]["participatiewet_uitkering"].append(dict(
                bsn=info["bsn"], regeling="algemene bijstand", startdatum=start, einddatum=eind,
                maandbedrag=round(rng.uniform(1050, 1650), 2)))
        # Overige zaken van inwoners.
        if lft >= 18:
            sinds = next((b["sinds"] for b in vbo_info[vid]["bewoners"] if b["pl_id"] == pl_id), None)
            if sinds and date(2018, 1, 1) <= sinds <= PEILDATUM:
                zaak("ZT-VERH", sinds, sinds + timedelta(days=rng.randint(0, 6)), info["bsn"], obj=vid,
                     resultaat="verwerkt")
            if rng.random() < 0.05:
                reg = PEILDATUM - timedelta(days=rng.randint(1, 700))
                eind = reg + timedelta(days=rng.randint(2, 25))
                zaak("ZT-PARK", reg, eind if eind <= PEILDATUM else None, info["bsn"], obj=vid,
                     resultaat="verleend" if eind <= PEILDATUM else None)
            if rng.random() < 0.04:
                reg = PEILDATUM - timedelta(days=rng.randint(1, 700))
                zaak("ZT-UITT", reg, min(reg + timedelta(days=rng.randint(0, 3)), PEILDATUM), info["bsn"],
                     resultaat="verstrekt")

    for vid, v in sorted(vbo_info.items()):
        if rng.random() < 0.025 and v.get("eigenaar"):
            reg = PEILDATUM - timedelta(days=rng.randint(10, 900))
            eind = reg + timedelta(days=rng.randint(25, 130))  # sommige ruim over de termijn
            e = v["eigenaar"]
            zaak("ZT-OMV", reg, eind if eind <= PEILDATUM else None,
                 e[1] if e[0] == "bsn" else None, e[1] if e[0] == "nnp" else None, v["pand"],
                 rng.choice(["verleend", "verleend", "verleend", "geweigerd"]) if eind <= PEILDATUM else None)

    # 5. Belastingen: OZB voor eigenaren, afvalstoffenheffing per huishouden.
    nr = 0
    for jaar in (2024, 2025, 2026):
        for vid, v in sorted(vbo_info.items()):
            if "woz" not in v:
                continue
            for soort, wie, bedrag in [
                ("OZB eigenaren", v["eigenaar"], v["woz"][jaar - 1] * (0.00045 if v["doel"] == "woonfunctie" else 0.0011)),
                ("afvalstoffenheffing", v["gebruiker"] if v["doel"] == "woonfunctie" else None,
                 (285 if len(v["bewoners"]) <= 1 else 365) * (1.03 ** (jaar - 2024))),
            ]:
                if not wie:
                    continue
                nr += 1
                status = "betaald"
                if soort == "afvalstoffenheffing" and wie[0] == "bsn" and wie[1] in bijstand:
                    status = "kwijtgescholden"
                    zaak("ZT-KWIJT", date(jaar, 3, 1) + timedelta(days=rng.randint(0, 60)),
                         date(jaar, 5, 15) + timedelta(days=rng.randint(0, 30)), wie[1], resultaat="toegekend")
                elif jaar == 2026 and rng.random() < 0.12:
                    status = "aanmaning verstuurd"  # in november nog niet betaald
                uit["belastingen"]["aanslag"].append(dict(
                    aanslagnummer=f"{jaar}{nr:08d}", belastingjaar=jaar, soort=soort,
                    subject_bsn=wie[1] if wie[0] == "bsn" else None, subject_nnp_id=wie[1] if wie[0] == "nnp" else None,
                    wozobjectnummer=woz_van_vbo.get(vid), bedrag=round(bedrag, 2), dagtekening=date(jaar, 2, 28),
                    status=status))

    # 6. Meldingen openbare ruimte, de afgelopen twee jaar.
    vbos = sorted(vbo_info.items())
    volwassenen = sorted({b["bsn"] for _, v in vbos for b in v["bewoners"] if (_leeftijd(b["geb"]) or 0) >= 18})
    for i in range(1, 3001):
        vid, v = rng.choice(vbos)
        hoofd, sub, dagen = rng.choice(MOR_CATEGORIEN)
        gemeld = datetime(2024, 12, 1, tzinfo=timezone.utc) + timedelta(minutes=rng.randint(0, 2 * 365 * 24 * 60))
        if gemeld.date() > PEILDATUM:
            gemeld = _dt(PEILDATUM - timedelta(days=rng.randint(0, 30)), 8)
        doorloop = timedelta(hours=rng.uniform(2, dagen * 24 * 2.2))
        klaar = gemeld + doorloop if (gemeld + doorloop).date() <= PEILDATUM else None
        status = "afgehandeld" if klaar else ("in behandeling" if rng.random() < 0.6 else "gemeld")
        sid = f"SIG-{i:06d}"
        uit["mor"]["melding"].append(dict(
            signaalnummer=sid, hoofdcategorie=hoofd, subcategorie=sub, omschrijving=f"{sub} (synthetische melding)",
            nummeraanduiding_identificatie=v["num"],
            locatie_wkt=f"POINT({round(v['x'] + rng.uniform(-25, 25), 1)} {round(v['y'] + rng.uniform(-25, 25), 1)})",
            melder_bsn=rng.choice(volwassenen) if volwassenen and rng.random() < 0.35 else None,
            aangemaakt_op=gemeld, status=status, afgehandeld_op=klaar))
        uit["mor"]["status"].append(dict(signaalnummer=sid, status="gemeld", tijdstip=gemeld))
        if status != "gemeld":
            uit["mor"]["status"].append(dict(signaalnummer=sid, status="in behandeling",
                                             tijdstip=gemeld + doorloop * rng.uniform(0.05, 0.4)))
        if klaar:
            uit["mor"]["status"].append(dict(signaalnummer=sid, status="afgehandeld", tijdstip=klaar))

    return uit, verslag


# --- Database --------------------------------------------------------------------------

def schrijf(con, uit):
    """Schema's aanmaken (idempotent), rechten en publicatie zetten, tabellen leeg en vullen."""
    from psycopg import sql  # pylint: disable=import-outside-toplevel
    with con.cursor() as cur:
        cur.execute(open(SQL_BESTAND, encoding="utf-8").read())
        for s in SCHEMAS:
            if s not in CDC_SCHEMAS:
                cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {s} FROM dlt_lezer; "
                                    "REVOKE USAGE ON SCHEMA {s} FROM dlt_lezer; "
                                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {s} REVOKE SELECT ON TABLES FROM dlt_lezer"
                                    ).format(s=sql.Identifier(s)))
                continue
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {s} TO dlt_lezer; "
                                "GRANT SELECT ON ALL TABLES IN SCHEMA {s} TO dlt_lezer; "
                                "ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT SELECT ON TABLES TO dlt_lezer").format(
                s=sql.Identifier(s)))
        # De publicaties voor CDC, met per tabel de kolommen (DF-ADR-006).
        import publicaties  # pylint: disable=import-outside-toplevel
        publicaties.zet(cur)
        # De Zaken-API leest met een eigen rol, alleen het schema zaken.
        wachtwoord = os.environ.get("ZAKEN_API_DB_WACHTWOORD")
        if wachtwoord:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'zaken_api'")
            cur.execute(sql.SQL("{} ROLE zaken_api LOGIN PASSWORD {}").format(
                sql.SQL("ALTER" if cur.fetchone() else "CREATE"), sql.Literal(wachtwoord)))
            cur.execute("GRANT CONNECT ON DATABASE bron TO zaken_api; GRANT USAGE ON SCHEMA zaken TO zaken_api; "
                        "GRANT SELECT ON ALL TABLES IN SCHEMA zaken TO zaken_api; "
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA zaken GRANT SELECT ON TABLES TO zaken_api")
        tabellen = [(s, t) for s in SCHEMAS for t in uit[s]]
        cur.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY").format(
            sql.SQL(", ").join(sql.Identifier(s, t) for s, t in tabellen)))
        for s, t in tabellen:
            rijen = uit[s][t]
            kolommen = list(rijen[0])
            cur.executemany(
                sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(s, t), sql.SQL(", ").join(map(sql.Identifier, kolommen)),
                    sql.SQL(", ").join(sql.Placeholder() * len(kolommen))),
                [[r[k] for k in kolommen] for r in rijen])
    con.commit()


def synthetisch(con):
    import inwoners  # pylint: disable=import-outside-toplevel
    import simulatie  # pylint: disable=import-outside-toplevel
    with con.cursor() as cur:
        n = inwoners.maak(cur, PEILDATUM, INWONERS, SEED)
        print(f"Synthetische inwoners: {n} huishoudens")
        personen, verblijf, gemeenten = lees_brp(cur)
    if not personen:
        raise SystemExit("De BRP is leeg. Eerst: bron.sh laden")
    uit, verslag = genereer(personen, verblijf, gemeenten)
    schrijf(con, uit)
    with con.cursor() as cur:
        simulatie.zet_klaar(cur)
    con.commit()
    print("Synthetische bronnen gemaakt (seed %d):" % SEED)
    for s in SCHEMAS:
        for t, rijen in sorted(uit[s].items()):
            print(f"  {s + '.' + t:34} {len(rijen):6} rijen")
    print("Bewuste afwijkingen tussen BAG en BRP (voor de kwaliteitscontrole):")
    for k, n in sorted(verslag.items()):
        print(f"  {k}: {n}")


def melding(con):
    """Een nieuwe melding, nu, op een willekeurig adres."""
    rng = random.Random()
    with con.cursor() as cur:
        cur.execute("SELECT n.identificatie, v.geometrie_wkt FROM bag.verblijfsobject v "
                    "JOIN bag.nummeraanduiding n ON n.identificatie = v.hoofdadres_identificatie "
                    "ORDER BY random() LIMIT 1")
        num, wkt = cur.fetchone()
        cur.execute("SELECT coalesce(max(substr(signaalnummer, 5)::int), 0) + 1 FROM mor.melding")
        sid = f"SIG-{cur.fetchone()[0]:06d}"
        hoofd, sub, _ = rng.choice(MOR_CATEGORIEN)
        nu = datetime.now(timezone.utc)
        cur.execute("INSERT INTO mor.melding (signaalnummer, hoofdcategorie, subcategorie, omschrijving, "
                    "nummeraanduiding_identificatie, locatie_wkt, aangemaakt_op, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 'gemeld')", (sid, hoofd, sub, f"{sub} (demo)", num, wkt, nu))
        cur.execute("INSERT INTO mor.status (signaalnummer, status, tijdstip) VALUES (%s, 'gemeld', %s)", (sid, nu))
    con.commit()
    print(f"Nieuwe melding {sid}: {hoofd} / {sub}, bij nummeraanduiding {num}")


def zaak_afhandelen(con):
    """Een open zaak afhandelen, nu."""
    with con.cursor() as cur:
        cur.execute("SELECT identificatie, zaaktype_identificatie FROM zaken.zaak WHERE einddatum IS NULL "
                    "ORDER BY registratiedatum LIMIT 1")
        rij = cur.fetchone()
        if not rij:
            raise SystemExit("Er is geen open zaak.")
        zid, zt = rij
        cur.execute("UPDATE zaken.zaak SET einddatum = current_date, resultaat = 'verleend', gewijzigd_op = now() "
                    "WHERE identificatie = %s", (zid,))
        cur.execute("INSERT INTO zaken.status (zaak_identificatie, statustype, datum_status_gezet) "
                    "VALUES (%s, 'Afgehandeld', now())", (zid,))
    con.commit()
    print(f"Zaak {zid} ({zt}) afgehandeld")
