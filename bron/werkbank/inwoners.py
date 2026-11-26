"""Synthetische inwoners in de BRP, naast de testpersonen van vrijBRP (DF-ADR-010).

De testpersonen zijn testgevallen; ze blijven zoals ze zijn. Voor een bevolking
waarin dagelijks iets gebeurt, komen er huishoudens bij: alleenstaanden, paren,
gezinnen, met ouders en kinderen over en weer in de categorieën 02, 03 en 09.
Ze wonen in dezelfde straten als de testpersonen, op huisnummers in de buurt
(zelfde postcode), zodat de BAG en de buurten van CBS kloppen.

Alle synthetische personen hebben testset 'synthetisch'. Hun BSN voldoet aan de
elfproef en ligt in een eigen reeks; namen zijn gewone Nederlandse namen.
"""

import random
from datetime import date, timedelta

TESTSET = "synthetisch"
BSN_START = 999100000
ANR_START = 9800000000
KERNGEMEENTEN = {"0518", "0599", "0363", "0344"}

VOORNAMEN_M = ["Jan", "Pieter", "Kees", "Henk", "Wim", "Joost", "Bas", "Thijs", "Daan", "Sem", "Lucas", "Milan",
               "Noah", "Finn", "Jesse", "Ruben", "Mohamed", "Youssef", "Ahmet", "Emre", "Mark", "Erik", "Johan",
               "Gerrit", "Hans", "Rik", "Tim", "Lars", "Sven", "Stijn", "Bram", "Luuk", "Levi", "Adam", "Mees",
               "Jayden", "Kevin", "Dennis", "Rob", "Frank"]
VOORNAMEN_V = ["Anna", "Maria", "Johanna", "Els", "Ingrid", "Marieke", "Sanne", "Lotte", "Emma", "Julia", "Sophie",
               "Tess", "Zoë", "Mila", "Noor", "Fleur", "Fatima", "Amira", "Elif", "Zeynep", "Linda", "Monique",
               "Petra", "Annemiek", "Karin", "Esther", "Laura", "Iris", "Eva", "Lisa", "Femke", "Anouk", "Sara",
               "Yara", "Nora", "Hanna", "Saskia", "Wendy", "Joke", "Ria"]
ACHTERNAMEN = [("", "Jansen"), ("de", "Vries"), ("van den", "Berg"), ("", "Bakker"), ("", "Visser"), ("", "Smit"),
               ("", "Meijer"), ("de", "Boer"), ("", "Mulder"), ("de", "Groot"), ("", "Bos"), ("", "Vos"),
               ("", "Peters"), ("", "Hendriks"), ("van", "Leeuwen"), ("", "Dekker"), ("", "Brouwer"), ("de", "Wit"),
               ("", "Dijkstra"), ("", "Smits"), ("de", "Graaf"), ("van der", "Meer"), ("van der", "Linden"),
               ("", "Kok"), ("", "Jacobs"), ("de", "Haan"), ("", "Vermeulen"), ("van den", "Heuvel"),
               ("van der", "Veen"), ("van den", "Broek"), ("de", "Bruijn"), ("de", "Jong"), ("", "Schouten"),
               ("van", "Beek"), ("", "Willems"), ("van", "Dijk"), ("", "Hoekstra"), ("", "Maas"), ("", "Verhoeven"),
               ("", "Koster"), ("", "Prins"), ("", "Huisman"), ("", "Postma"), ("", "Kuipers"), ("", "Yilmaz"),
               ("", "El Amrani"), ("", "Öztürk"), ("", "Bouzid"), ("", "Nguyen"), ("", "Pinas")]


def elfproef(nummer):
    s = f"{nummer:09d}"
    return (sum(int(c) * (9 - i) for i, c in enumerate(s[:8])) - int(s[8])) % 11 == 0


def d8(d):
    return d.strftime("%Y%m%d")


class Nummers:
    """Uitgifte van BSN en A-nummer, zonder botsing met wat er al is."""

    def __init__(self, cur):
        cur.execute("SELECT burgerservicenummer, a_nummer FROM brp.persoonslijst")
        rijen = cur.fetchall()
        self.bsns = {r[0] for r in rijen if r[0]}
        self.anrs = {r[1] for r in rijen if r[1]}
        synth = [int(b) for b in self.bsns if b and b.isdigit() and BSN_START <= int(b) < BSN_START + 10**6]
        self.volgende_bsn = max(synth, default=BSN_START) + 1
        synth_a = [int(a) for a in self.anrs if a and a.isdigit() and int(a) >= ANR_START]
        self.volgende_anr = max(synth_a, default=ANR_START) + 1

    def bsn(self):
        while not elfproef(self.volgende_bsn) or f"{self.volgende_bsn:09d}" in self.bsns:
            self.volgende_bsn += 1
        b = f"{self.volgende_bsn:09d}"
        self.bsns.add(b)
        self.volgende_bsn += 1
        return b

    def anr(self):
        while str(self.volgende_anr) in self.anrs:
            self.volgende_anr += 1
        a = str(self.volgende_anr)
        self.anrs.add(a)
        self.volgende_anr += 1
        return a


def rij(cur, tabel, pl_id, stapel, volgnr, **velden):
    velden = {k: v for k, v in velden.items() if v not in (None, "")}
    k = list(velden)
    cur.execute(f"INSERT INTO brp.{tabel} (pl_id, stapel, volgnr, actueel, {', '.join(k)}) "
                f"VALUES (%s, %s, %s, true, {', '.join(['%s'] * len(k))})",
                [pl_id, stapel, volgnr] + [velden[x] for x in k])


def volgende_stapel(cur, tabel, pl_id):
    cur.execute(f"SELECT coalesce(max(stapel), 0) + 1 FROM brp.{tabel} WHERE pl_id = %s", (pl_id,))
    return cur.fetchone()[0]


def nieuw_persoon(rng, geslacht, geboren, achternaam=None):
    vv, naam = achternaam or rng.choice(ACHTERNAMEN)
    voornaam = rng.choice(VOORNAMEN_M if geslacht == "M" else VOORNAMEN_V)
    if rng.random() < 0.4:
        voornaam += " " + rng.choice(VOORNAMEN_M if geslacht == "M" else VOORNAMEN_V)
    return dict(geslacht=geslacht, geboren=geboren, voornamen=voornaam, voorvoegsel=vv, geslachtsnaam=naam)


def schrijf_persoon(cur, nummers, p, adres, ingeschreven, opneming, gemeente_geboorte=None, land_vanwaar=None):
    """Een persoonslijst met persoon (01), nationaliteit (04), inschrijving (07) en verblijfplaats (08)."""
    p["bsn"], p["anr"] = nummers.bsn(), nummers.anr()
    cur.execute("INSERT INTO brp.persoonslijst (a_nummer, burgerservicenummer, testsets) VALUES (%s, %s, %s) "
                "RETURNING id", (p["anr"], p["bsn"], [TESTSET]))
    p["pl_id"] = pl_id = cur.fetchone()[0]
    gem = adres["gemeente_van_inschrijving"]
    rij(cur, "persoon", pl_id, 1, 1, a_nummer=p["anr"], burgerservicenummer=p["bsn"], voornamen=p["voornamen"],
        voorvoegsel_geslachtsnaam=p["voorvoegsel"], geslachtsnaam=p["geslachtsnaam"], geboortedatum=d8(p["geboren"]),
        geboorteplaats=gemeente_geboorte or gem, geboorteland="6030", geslachtsaanduiding=p["geslacht"],
        ingangsdatum_geldigheid=d8(p["geboren"]), datum_van_opneming=d8(opneming))
    rij(cur, "nationaliteit", pl_id, 1, 1, nationaliteit="0001", reden_opname_nationaliteit="001",
        ingangsdatum_geldigheid=d8(p["geboren"]), datum_van_opneming=d8(opneming))
    rij(cur, "inschrijving", pl_id, 1, 1, datum_eerste_inschrijving_gba=d8(max(p["geboren"], date(1994, 10, 1))),
        gemeente_waar_de_pk_zich_bevindt=gem, indicatie_geheim="0", versienummer="0001",
        datum_van_opneming=d8(opneming))
    rij(cur, "verblijfplaats", pl_id, 1, 1, **adres, datum_inschrijving=d8(ingeschreven), functie_adres="W",
        datum_aanvang_adreshouding=d8(ingeschreven), omschrijving_van_de_aangifte_adreshouding="I",
        land_vanwaar_ingeschreven=land_vanwaar, datum_vestiging_in_nederland=d8(ingeschreven) if land_vanwaar else None,
        ingangsdatum_geldigheid=d8(ingeschreven), datum_van_opneming=d8(opneming))
    return p


def familie(cur, ouders, kinderen, opneming):
    """Ouders (02, 03) bij de kinderen en kinderen (09) bij de ouders."""
    for kind in kinderen:
        for i, ouder in enumerate(ouders[:2]):
            rij(cur, "ouder_1" if i == 0 else "ouder_2", kind["pl_id"], 1, 1, a_nummer=ouder["anr"],
                burgerservicenummer=ouder["bsn"], voornamen=ouder["voornamen"],
                voorvoegsel_geslachtsnaam=ouder["voorvoegsel"], geslachtsnaam=ouder["geslachtsnaam"],
                geboortedatum=d8(ouder["geboren"]), geslachtsaanduiding=ouder["geslacht"],
                datum_ingang_familierechtelijke_betrekking=d8(kind["geboren"]),
                ingangsdatum_geldigheid=d8(kind["geboren"]), datum_van_opneming=d8(opneming))
        for ouder in ouders:
            rij(cur, "kind", ouder["pl_id"], volgende_stapel(cur, "kind", ouder["pl_id"]), 1, a_nummer=kind["anr"],
                burgerservicenummer=kind["bsn"], voornamen=kind["voornamen"],
                voorvoegsel_geslachtsnaam=kind["voorvoegsel"], geslachtsnaam=kind["geslachtsnaam"],
                geboortedatum=d8(kind["geboren"]), ingangsdatum_geldigheid=d8(kind["geboren"]),
                datum_van_opneming=d8(opneming))


def huwelijk(cur, a, b, datum, opneming):
    for x, y in ((a, b), (b, a)):
        rij(cur, "huwelijk", x["pl_id"], volgende_stapel(cur, "huwelijk", x["pl_id"]), 1, a_nummer=y["anr"],
            burgerservicenummer=y["bsn"], voornamen=y["voornamen"], voorvoegsel_geslachtsnaam=y["voorvoegsel"],
            geslachtsnaam=y["geslachtsnaam"], geboortedatum=d8(y["geboren"]), geslachtsaanduiding=y["geslacht"],
            datum_huwelijkssluiting_aangaan_gps=d8(datum), plaats_huwelijkssluiting_aangaan_gps=
            "0363", land_huwelijkssluiting_aangaan_gps="6030", soort_verbintenis="H",
            ingangsdatum_geldigheid=d8(datum), datum_van_opneming=d8(opneming))


def _jaren(rng, vandaag, lo, hi):
    return vandaag - timedelta(days=rng.randint(lo * 365, hi * 365 + 364))


def huishouden(cur, rng, nummers, adres, vandaag, verhuisd=None, land_vanwaar=None):
    """Eén huishouden op een adres. verhuisd: datum van inschrijving (anders willekeurig in het verleden).
    Geeft de personen terug."""
    soort = rng.choices(["alleen", "paar", "gezin", "eenouder"], weights=[34, 30, 28, 8])[0]
    personen, kinderen, ouders = [], [], []
    if soort == "alleen":
        g = rng.choice("MV")
        leeftijd = rng.choices([(19, 29), (30, 49), (50, 69), (70, 95)], weights=[30, 25, 20, 25])[0]
        ouders = [nieuw_persoon(rng, g, _jaren(rng, vandaag, *leeftijd))]
    else:
        lo, hi = {"paar": (23, 85), "gezin": (27, 52), "eenouder": (24, 52)}[soort]
        a = nieuw_persoon(rng, "V", _jaren(rng, vandaag, lo, hi))
        ouders = [a]
        if soort != "eenouder":
            g = "M" if rng.random() < 0.95 else "V"
            ouders.append(nieuw_persoon(rng, g, a["geboren"] + timedelta(days=rng.randint(-6 * 365, 4 * 365))))
        if soort in ("gezin", "eenouder"):
            jongste_ouder = max(o["geboren"] for o in ouders)
            naam = (ouders[-1]["voorvoegsel"], ouders[-1]["geslachtsnaam"])
            for _ in range(rng.choices([1, 2, 3], weights=[40, 45, 15])[0]):
                geboren = jongste_ouder + timedelta(days=rng.randint(22 * 365, 40 * 365))
                if geboren < vandaag - timedelta(days=30):
                    kinderen.append(nieuw_persoon(rng, rng.choice("MV"), geboren, naam))
    volwassen = max(o["geboren"] for o in ouders) + timedelta(days=18 * 365)
    inschrijving = verhuisd or max(volwassen, vandaag - timedelta(days=rng.randint(30, 25 * 365)))
    for p in ouders + kinderen:
        schrijf_persoon(cur, nummers, p, adres, max(inschrijving, p["geboren"]), vandaag, land_vanwaar=land_vanwaar)
        personen.append(p)
    if len(ouders) == 2 and rng.random() < 0.6:
        huwelijk(cur, ouders[0], ouders[1], max(o["geboren"] for o in ouders) + timedelta(days=rng.randint(
            23 * 365, 33 * 365)), vandaag)
    if kinderen:
        familie(cur, ouders, kinderen, vandaag)
    return personen


ADRESVELDEN = ["gemeente_van_inschrijving", "code_gemeente_van_inschrijving", "straatnaam", "openbare_ruimte",
               "huisnummer", "huisletter", "huisnummertoevoeging", "postcode", "woonplaatsnaam",
               "identificatie_verblijfplaats", "identificatiecode_nummeraanduiding"]


def verwijder(cur):
    """Alle synthetische personen weg (ook wie de simulatie erbij maakte)."""
    cur.execute("SELECT table_name FROM information_schema.columns WHERE table_schema = 'brp' AND column_name = 'pl_id'")
    for (t,) in cur.fetchall():
        cur.execute(f"DELETE FROM brp.{t} WHERE pl_id IN (SELECT id FROM brp.persoonslijst "
                    "WHERE %s = ANY(testsets))", (TESTSET,))
    cur.execute("DELETE FROM brp.persoonslijst WHERE %s = ANY(testsets)", (TESTSET,))


def maak(cur, vandaag, huishoudens=1500, seed=0):
    """Synthetische huishoudens op huisnummers rond de adressen van de testpersonen."""
    rng = random.Random(f"inwoners-{seed}")
    verwijder(cur)
    nummers = Nummers(cur)
    cur.execute(f"""
        SELECT DISTINCT ON (postcode, huisnummer, coalesce(huisletter, ''), coalesce(huisnummertoevoeging, ''))
               {', '.join(ADRESVELDEN)}
        FROM brp.verblijfplaats
        WHERE actueel AND postcode ~ '^[0-9]{{4}}[A-Z]{{2}}$' AND huisnummer ~ '^[0-9]+$'
          AND coalesce(land_waarnaar_vertrokken, '') = '' AND gemeente_van_inschrijving ~ '^[0-9]{{4}}$'
        ORDER BY postcode, huisnummer, coalesce(huisletter, ''), coalesce(huisnummertoevoeging, '')""")
    namen = [d[0] for d in cur.description]
    basis = [dict(zip(namen, r)) for r in cur.fetchall()]
    if not basis:
        return 0
    bezet = {(a["postcode"], int(a["huisnummer"])) for a in basis}
    gewicht = [4 if a["gemeente_van_inschrijving"] in KERNGEMEENTEN else 1 for a in basis]
    n = 0
    for _ in range(huishoudens * 3):
        if n >= huishoudens:
            break
        b = rng.choices(basis, weights=gewicht)[0]
        nr = int(b["huisnummer"]) + rng.choice([-10, -8, -6, -4, -2, 2, 4, 6, 8, 10, 12, 14])
        if nr < 1 or (b["postcode"], nr) in bezet:
            continue
        bezet.add((b["postcode"], nr))
        adres = dict(b, huisnummer=str(nr), huisletter=None, huisnummertoevoeging=None,
                     identificatie_verblijfplaats=None, identificatiecode_nummeraanduiding=None)
        huishouden(cur, rng, nummers, adres, vandaag)
        n += 1
    return n
