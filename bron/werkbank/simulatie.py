"""Simulatieklok: de gemeente leeft door, uur na uur (DF-ADR-014).

Vanaf 27 november 2026 maakt dit script elk uur de mutaties die een gemeente in
dat uur zou zien, een jaar lang:

  BRP          geboorte, overlijden, verhuizing binnen de gemeente, vestiging van
               buiten, vertrek naar het buitenland (alleen synthetische inwoners)
  BAG          bouwprojecten: vergunning, bouw gestart, in gebruik, ingemeten
  WOZ          nieuwe waarden op 1 januari; eigenaar en gebruiker volgen de BRP
  belastingen  aanslagen eind februari, betalingen, aanmaningen, kwijtschelding
  mor          meldingen met een seizoen (blad, gladheid, vuurwerk) en afhandeling
  zaken        nieuwe zaken en hun statusverloop, binnen kantoortijd
  sociaal      Wmo na toekenning, jeugdhulp en bijstand die beginnen en eindigen

Elk uur heeft een eigen seed (vaste seed + tijdstip). De stand in sim.voortgang
zegt tot waar de klok is; een stap verwerkt alle uren tot nu, ook als dfw een
tijd uit heeft gestaan. Er wordt nooit iets verwijderd: een einde is een
einddatum of een nieuwe status, zoals in een echte registratie.

    python brp.py simuleer [TOT]     de klok bijwerken tot nu (of tot TOT, voor tests)
    python brp.py simulatie-status   tot waar de klok is, en wat er laatst gebeurde
"""

import collections
import math
import random
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import inwoners as I
import synthetisch as S

TZ = ZoneInfo("Europe/Amsterdam")
START = datetime(2026, 11, 27, tzinfo=TZ)
EIND = datetime(2027, 11, 27, tzinfo=TZ)

SQL = """
CREATE SCHEMA IF NOT EXISTS sim;
CREATE TABLE IF NOT EXISTS sim.voortgang (id int PRIMARY KEY CHECK (id = 1), tot timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS sim.logboek (id bigserial PRIMARY KEY, tijdstip timestamptz NOT NULL,
  soort text NOT NULL, tekst text NOT NULL);
CREATE TABLE IF NOT EXISTS sim.bouwproject (pand text PRIMARY KEY, gemeente text NOT NULL, start date NOT NULL,
  gereed date NOT NULL, fase text NOT NULL);
CREATE TABLE IF NOT EXISTS sim.export (bron text PRIMARY KEY, tot timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS verblijfplaats_adres ON brp.verblijfplaats (postcode, huisnummer) WHERE actueel;
CREATE INDEX IF NOT EXISTS zaak_open ON zaken.zaak (identificatie) WHERE einddatum IS NULL;
CREATE INDEX IF NOT EXISTS melding_open ON mor.melding (signaalnummer) WHERE status <> 'afgehandeld';
CREATE INDEX IF NOT EXISTS status_zaak ON zaken.status (zaak_identificatie);
"""

# Kans per uur over de dag: burgers melden overdag en 's avonds.
BURGER = [0.2, 0.1, 0.1, 0.1, 0.1, 0.3, 0.8, 1.5, 2.0, 2.0, 1.8, 1.7, 1.6, 1.6, 1.6, 1.7, 1.8, 1.8, 1.7, 1.5,
          1.2, 0.9, 0.6, 0.4]
BURGER = [x / sum(BURGER) for x in BURGER]

# Per dag gemiddeld (over de hele week), voor ongeveer 4.000 inwoners.
TEMPO = {"geboorte": 0.12, "overlijden": 0.09, "verhuizing": 0.9, "vestiging": 0.22, "vertrek": 0.15,
         "melding": 4.5, "ZT-PARK": 0.15, "ZT-UITT": 0.12, "ZT-OMV": 0.06, "ZT-EVEN": 0.05, "ZT-WMO": 0.10,
         "ZT-KWIJT": 0.03, "jeugdhulp": 0.025, "bijstand": 0.03, "bouwproject": 1 / 45}
SEIZOEN = {  # subcategorie of zaaktype: maand -> factor
    "Boom": {10: 3, 11: 4, 12: 1.5}, "Onkruid": {5: 2, 6: 3, 7: 3, 8: 2, 12: 0.2, 1: 0.2, 2: 0.2},
    "Lantaarnpaal kapot": {11: 2, 12: 2.5, 1: 2.5, 2: 1.5}, "Zwerfafval": {1: 3, 7: 1.5},
    "Grofvuil": {1: 2.5, 4: 1.5}, "Jongeren": {6: 1.5, 7: 2, 8: 2, 12: 2.5}, "Geluid": {6: 2, 7: 2.5, 8: 2},
    "Gladheid": {m: 0 for m in range(1, 13)} | {11: 0.15, 12: 0.9, 1: 1.2, 2: 0.75, 3: 0.15}, "ZT-EVEN": {3: 2, 4: 3, 5: 3, 6: 2},
    "ZT-KWIJT": {3: 5, 4: 4, 5: 2},
}
MOR = S.MOR_CATEGORIEN + [("Wegen, verkeer, straatmeubilair", "Gladheid", 1)]
RESULTAAT = {"ZT-WMO": [("toegekend", 80), ("afgewezen", 20)], "ZT-OMV": [("verleend", 85), ("geweigerd", 15)],
             "ZT-PARK": [("verleend", 95), ("geweigerd", 5)], "ZT-EVEN": [("verleend", 90), ("geweigerd", 10)],
             "ZT-UITT": [("verstrekt", 1)], "ZT-VERH": [("verwerkt", 1)],
             "ZT-KWIJT": [("toegekend", 70), ("afgewezen", 30)]}
LANDEN = [("5010", "België"), ("6029", "Duitsland"), ("6037", "Spanje"), ("6043", "Turkije"), ("7028", "Polen"),
          ("5022", "Marokko")]
NIEUWE_STRATEN = ["Klaprooslaan", "Korenbloemstraat", "Zilverschoonhof", "Pinksterbloemweg", "Boterbloemlaan",
                  "Fluitekruidstraat", "Ijsvogelhof", "Grutto-erf", "Kievitlaan", "Tureluurstraat", "Lepelaarhof",
                  "Wilgenroosje", "Dotterbloemkade", "Zwanebloemlaan", "Watermunthof", "Kamillestraat"]
WOON = "Verblijfsobject in gebruik"


def poisson(rng, lam):
    if lam <= 0:
        return 0
    grens, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= grens:
            return k
        k += 1


def kantoor(t):
    """Gewicht van dit uur binnen kantoortijd (ma-vr 8-17); per dag gemiddeld 1 over de week."""
    return 7 / 5 / 9 if t.weekday() < 5 and 8 <= t.hour < 17 else 0


def seizoen(sleutel, maand):
    return SEIZOEN.get(sleutel, {}).get(maand, 1)


def d8(d):
    return d.strftime("%Y%m%d")


def leeftijd(geb, op):
    return op.year - geb.year - ((op.month, op.day) < (geb.month, geb.day))


def brp_datum(s):
    return S._datum(s)  # pylint: disable=protected-access


class Uur:
    """Alles wat in één uur gebeurt, met de cursor en de seed van dat uur."""

    def __init__(self, cur, t):
        self.cur, self.t, self.dag = cur, t, t.date()
        self.rng = random.Random(f"{S.SEED}-{t.astimezone(timezone.utc).isoformat()}")
        self.teller = collections.Counter()

    # --- hulpmiddelen ---------------------------------------------------------------

    def moment(self):
        return self.t + timedelta(minutes=self.rng.randint(0, 59), seconds=self.rng.randint(0, 59))

    def rijen(self, sql, args=()):
        self.cur.execute(sql, args)
        namen = [d[0] for d in self.cur.description]
        return [dict(zip(namen, r)) for r in self.cur.fetchall()]

    def log(self, soort, tekst):
        self.teller[soort] += 1
        self.cur.execute("INSERT INTO sim.logboek (tijdstip, soort, tekst) VALUES (%s, %s, %s)",
                         (self.moment(), soort, tekst))

    def inwoners(self, alleen_synthetisch=False):
        rijen = self.rijen(f"""
            SELECT DISTINCT ON (pl.id) pl.id AS pl_id, pl.burgerservicenummer AS bsn, p.geboortedatum,
                   p.geslachtsaanduiding AS geslacht, v.postcode, v.huisnummer, coalesce(v.huisletter, '') AS letter,
                   coalesce(v.huisnummertoevoeging, '') AS toev, v.gemeente_van_inschrijving AS gemeente,
                   %s = ANY(pl.testsets) AS synthetisch
            FROM brp.persoonslijst pl
            JOIN brp.persoon p ON p.pl_id = pl.id AND p.actueel
            JOIN brp.verblijfplaats v ON v.pl_id = pl.id AND v.actueel
            WHERE NOT EXISTS (SELECT 1 FROM brp.overlijden o WHERE o.pl_id = pl.id AND o.actueel)
              AND coalesce(v.land_waarnaar_vertrokken, '') = '' AND v.postcode <> ''
              AND pl.burgerservicenummer IS NOT NULL
              {"AND %s = ANY(pl.testsets)" if alleen_synthetisch else ""}
            ORDER BY pl.id, p.stapel, v.stapel DESC""",
            (I.TESTSET, I.TESTSET) if alleen_synthetisch else (I.TESTSET,))
        uit = []
        for r in rijen:
            r["geboren"] = brp_datum(r["geboortedatum"])
            if r["geboren"]:
                r["leeftijd"] = leeftijd(r["geboren"], self.dag)
                r["adres"] = (r["postcode"], r["huisnummer"], r["letter"], r["toev"])
                uit.append(r)
        return uit

    def volwassenen(self, lo=18, hi=120):
        return [p for p in self.inwoners() if lo <= p["leeftijd"] <= hi]

    def vrije_woningen(self, gemeente=None):
        return self.rijen(f"""
            SELECT v.identificatie AS vbo, n.identificatie AS num, n.postcode, n.huisnummer, n.huisletter,
                   n.huisnummertoevoeging, o.naam AS straat, w.naam AS woonplaats, w.gemeentecode AS gemeente
            FROM bag.verblijfsobject v
            JOIN bag.nummeraanduiding n ON n.identificatie = v.hoofdadres_identificatie
            JOIN bag.openbare_ruimte o ON o.identificatie = n.openbare_ruimte_identificatie
            JOIN bag.woonplaats w ON w.identificatie = o.woonplaats_identificatie
            WHERE v.gebruiksdoel = 'woonfunctie' AND v.status LIKE '{WOON}%%' AND n.postcode IS NOT NULL
              {"AND w.gemeentecode = %s" if gemeente else ""}
              AND NOT EXISTS (
                SELECT 1 FROM brp.verblijfplaats b
                WHERE b.actueel AND b.postcode = n.postcode AND b.huisnummer = n.huisnummer::text
                  AND coalesce(b.huisletter, '') = coalesce(n.huisletter, '')
                  AND coalesce(b.huisnummertoevoeging, '') = coalesce(n.huisnummertoevoeging, '')
                  AND coalesce(b.land_waarnaar_vertrokken, '') = ''
                  AND NOT EXISTS (SELECT 1 FROM brp.overlijden o2 WHERE o2.pl_id = b.pl_id AND o2.actueel))
            ORDER BY v.identificatie""", (gemeente,) if gemeente else ())

    @staticmethod
    def brp_adres(w):
        return dict(gemeente_van_inschrijving=w["gemeente"], code_gemeente_van_inschrijving=w["gemeente"],
                    straatnaam=w["straat"], openbare_ruimte=w["straat"], huisnummer=str(w["huisnummer"]),
                    huisletter=w["huisletter"], huisnummertoevoeging=w["huisnummertoevoeging"],
                    postcode=w["postcode"], woonplaatsnaam=w["woonplaats"], identificatie_verblijfplaats=w["vbo"],
                    identificatiecode_nummeraanduiding=w["num"])

    def vbo_bij(self, adres):
        postcode, nr, letter, toev = adres
        if not (nr and str(nr).isdigit()):
            return None
        self.cur.execute("""SELECT v.identificatie FROM bag.nummeraanduiding n
            JOIN bag.verblijfsobject v ON v.hoofdadres_identificatie = n.identificatie
            WHERE n.postcode = %s AND n.huisnummer = %s AND coalesce(n.huisletter, '') = %s
              AND coalesce(n.huisnummertoevoeging, '') = %s LIMIT 1""", (postcode, int(nr), letter, toev))
        r = self.cur.fetchone()
        return r[0] if r else None

    def persoon(self, pl_id):
        r = self.rijen("""SELECT pl.id AS pl_id, pl.a_nummer AS anr, pl.burgerservicenummer AS bsn, p.voornamen,
                                 coalesce(p.voorvoegsel_geslachtsnaam, '') AS voorvoegsel, p.geslachtsnaam,
                                 p.geboortedatum, p.geslachtsaanduiding AS geslacht
                          FROM brp.persoonslijst pl JOIN brp.persoon p ON p.pl_id = pl.id AND p.actueel
                          WHERE pl.id = %s LIMIT 1""", (pl_id,))[0]
        r["geboren"] = brp_datum(r["geboortedatum"])
        return r

    def raak(self, pl_id):
        self.cur.execute("UPDATE brp.persoonslijst SET gewijzigd_op = now() WHERE id = %s", (pl_id,))

    # --- BRP -----------------------------------------------------------------------

    def nieuw_verblijf(self, pl_id, adres=None, land=None):
        """Nieuw actueel record in categorie 08; het oude wordt historie."""
        oud = self.rijen("SELECT * FROM brp.verblijfplaats WHERE pl_id = %s AND actueel ORDER BY stapel DESC LIMIT 1",
                         (pl_id,))[0]
        leeg = I.ADRESVELDEN + ["straatnaam_officieel", "straatnaam_nen", "gemeentedeel", "aanduiding_bij_huisnummer",
                                "locatiebeschrijving", "land_waarnaar_vertrokken", "datum_vertrek_uit_nederland",
                                "adres_buitenland_waarnaar_vertrokken_1", "land_vanwaar_ingeschreven",
                                "datum_vestiging_in_nederland"]
        nieuw = {k: v for k, v in oud.items() if k not in ("id", "gewijzigd_op", "volgnr") and k not in leeg}
        vandaag = d8(self.dag)
        if adres:
            nieuw.update(adres, functie_adres="W", datum_aanvang_adreshouding=vandaag,
                         omschrijving_van_de_aangifte_adreshouding="I")
            if adres["gemeente_van_inschrijving"] != oud["gemeente_van_inschrijving"]:
                nieuw["datum_inschrijving"] = vandaag
        else:
            nieuw.update(gemeente_van_inschrijving="1999", code_gemeente_van_inschrijving="1999",
                         land_waarnaar_vertrokken=land, datum_vertrek_uit_nederland=vandaag,
                         adres_buitenland_waarnaar_vertrokken_1="Onbekend", functie_adres=None,
                         datum_aanvang_adreshouding=None, omschrijving_van_de_aangifte_adreshouding=None)
        nieuw.update(actueel=True, onjuist=False, ingangsdatum_geldigheid=vandaag, datum_van_opneming=vandaag)
        self.cur.execute("SELECT max(volgnr) + 1 FROM brp.verblijfplaats WHERE pl_id = %s AND stapel = %s",
                         (pl_id, oud["stapel"]))
        nieuw["volgnr"] = self.cur.fetchone()[0]
        self.cur.execute("UPDATE brp.verblijfplaats SET actueel = false, gewijzigd_op = now() WHERE id = %s",
                         (oud["id"],))
        nieuw = {k: v for k, v in nieuw.items() if v is not None}
        k = list(nieuw)
        self.cur.execute(f"INSERT INTO brp.verblijfplaats ({', '.join(k)}) VALUES ({', '.join(['%s'] * len(k))})",
                         [nieuw[x] for x in k])
        self.raak(pl_id)
        return (oud["postcode"], oud["huisnummer"], oud["huisletter"] or "", oud["huisnummertoevoeging"] or "")

    def huisgenoten(self, p, iedereen):
        return [q for q in iedereen if q["adres"] == p["adres"] and q["synthetisch"]]

    def geboorte(self):
        iedereen = self.inwoners(alleen_synthetisch=True)
        moeders = [p for p in iedereen if p["geslacht"] == "V" and 20 <= p["leeftijd"] <= 44]
        if not moeders:
            return
        moeder = self.rng.choices(moeders, weights=[math.exp(-((p["leeftijd"] - 31) / 6) ** 2) for p in moeders])[0]
        vader = next((q for q in self.huisgenoten(moeder, iedereen)
                      if q["geslacht"] == "M" and 18 <= q["leeftijd"] <= 65), None)
        ouders = [self.persoon(moeder["pl_id"])] + ([self.persoon(vader["pl_id"])] if vader else [])
        adres = self.rijen(f"SELECT {', '.join(I.ADRESVELDEN)} FROM brp.verblijfplaats WHERE pl_id = %s AND actueel "
                           "ORDER BY stapel DESC LIMIT 1", (moeder["pl_id"],))[0]
        geboren = self.dag - timedelta(days=self.rng.randint(1, 4))
        naam = (ouders[-1]["voorvoegsel"], ouders[-1]["geslachtsnaam"])
        kind = I.nieuw_persoon(self.rng, self.rng.choice("MV"), geboren, naam)
        nummers = I.Nummers(self.cur)
        I.schrijf_persoon(self.cur, nummers, kind, adres, geboren, self.dag)
        I.familie(self.cur, ouders, [kind], self.dag)
        for o in ouders:
            self.raak(o["pl_id"])
        self.log("geboorte", f"{kind['voornamen']} {kind['geslachtsnaam']} (BSN {kind['bsn']}), "
                             f"{adres['postcode']} {adres['huisnummer']}")

    def overlijden(self):
        iedereen = self.inwoners(alleen_synthetisch=True)
        if not iedereen:
            return
        p = self.rng.choices(iedereen, weights=[math.exp(0.1 * (q["leeftijd"] - 80)) for q in iedereen])[0]
        datum = self.dag - timedelta(days=self.rng.randint(1, 3))
        self.cur.execute("INSERT INTO brp.overlijden (pl_id, stapel, volgnr, actueel, datum_overlijden, "
                         "plaats_overlijden, land_overlijden, ingangsdatum_geldigheid, datum_van_opneming) "
                         "VALUES (%s, 1, 1, true, %s, %s, '6030', %s, %s)",
                         (p["pl_id"], d8(datum), p["gemeente"], d8(datum), d8(self.dag)))
        self.cur.execute("UPDATE brp.inschrijving SET datum_opschorting_bijhouding = %s, "
                         "omschrijving_reden_opschorting_bijhouding = 'O', gewijzigd_op = now() "
                         "WHERE pl_id = %s AND actueel", (d8(datum), p["pl_id"]))
        self.raak(p["pl_id"])
        self.einde_sociaal(p["bsn"], datum)
        self.woz_volgt([p["adres"]])
        self.log("overlijden", f"BSN {p['bsn']}, {p['leeftijd']} jaar, {p['postcode']} {p['huisnummer']}")

    def verhuizing(self):
        iedereen = self.inwoners(alleen_synthetisch=True)
        volwassen = [p for p in iedereen if p["leeftijd"] >= 18]
        if not volwassen:
            return
        p = self.rng.choice(volwassen)
        vrij = self.vrije_woningen(p["gemeente"])
        if not vrij:
            return
        woning = self.rng.choice(vrij)
        if self.rng.random() < 0.7:
            wie = self.huisgenoten(p, iedereen) or [p]
        else:
            wie = [p]  # uit huis, of uit elkaar
        oud = None
        for q in wie:
            oud = self.nieuw_verblijf(q["pl_id"], self.brp_adres(woning))
        self.zaak("ZT-VERH", p["bsn"], obj=woning["vbo"])
        self.woz_volgt([oud, (woning["postcode"], str(woning["huisnummer"]), woning["huisletter"] or "",
                              woning["huisnummertoevoeging"] or "")])
        self.log("verhuizing", f"{len(wie)} persoon/personen van {oud[0]} {oud[1]} naar {woning['postcode']} "
                               f"{woning['huisnummer']}")

    def vestiging(self):
        vrij = self.vrije_woningen()
        if not vrij:
            return
        woning = self.rng.choice(vrij)
        land = self.rng.choice(LANDEN)[0] if self.rng.random() < 0.25 else None
        personen = I.huishouden(self.cur, self.rng, I.Nummers(self.cur), self.brp_adres(woning), self.dag,
                                verhuisd=self.dag, land_vanwaar=land)
        oudste = min(personen, key=lambda p: p["geboren"])
        self.zaak("ZT-VERH", oudste["bsn"], obj=woning["vbo"])
        self.woz_volgt([(woning["postcode"], str(woning["huisnummer"]), woning["huisletter"] or "",
                         woning["huisnummertoevoeging"] or "")])
        self.log("vestiging", f"{len(personen)} persoon/personen{' uit het buitenland' if land else ''} op "
                              f"{woning['postcode']} {woning['huisnummer']}")

    def vertrek(self):
        iedereen = self.inwoners(alleen_synthetisch=True)
        volwassen = [p for p in iedereen if 18 <= p["leeftijd"] <= 70]
        if not volwassen:
            return
        p = self.rng.choice(volwassen)
        wie = self.huisgenoten(p, iedereen) if self.rng.random() < 0.6 else [p]
        land, naam = self.rng.choice(LANDEN)
        for q in wie:
            self.nieuw_verblijf(q["pl_id"], land=land)
            self.cur.execute("UPDATE brp.inschrijving SET datum_opschorting_bijhouding = %s, "
                             "omschrijving_reden_opschorting_bijhouding = 'E', gewijzigd_op = now() "
                             "WHERE pl_id = %s AND actueel", (d8(self.dag), q["pl_id"]))
            self.einde_sociaal(q["bsn"], self.dag)
        self.woz_volgt([p["adres"]])
        self.log("vertrek", f"{len(wie)} persoon/personen van {p['postcode']} {p['huisnummer']} naar {naam}")

    # --- WOZ volgt de BRP -------------------------------------------------------------

    def woz_volgt(self, adressen):
        """Na een verhuizing of overlijden: gebruiker (en soms eigenaar) van de WOZ-objecten bijwerken."""
        iedereen = None
        for adres in adressen:
            vbo = adres and self.vbo_bij(adres)
            if not vbo:
                continue
            self.cur.execute("SELECT wozobjectnummer FROM woz.object WHERE verblijfsobject_identificatie = %s", (vbo,))
            r = self.cur.fetchone()
            if not r:
                continue
            wnr = r[0]
            iedereen = iedereen if iedereen is not None else self.inwoners()
            bewoners = sorted((p for p in iedereen if p["adres"] == adres and p["leeftijd"] >= 18),
                              key=lambda p: p["geboren"])
            huidig = {row["rol"]: row for row in self.rijen(
                "SELECT id, rol, bsn, nnp_id FROM woz.belanghebbende WHERE wozobjectnummer = %s AND einddatum IS NULL",
                (wnr,))}
            nieuwe_gebruiker = bewoners[0]["bsn"] if bewoners else None
            g = huidig.get("gebruiker")
            if (g and g["bsn"]) != nieuwe_gebruiker:
                if g:
                    self.beeindig_belang(g["id"])
                if nieuwe_gebruiker:
                    self.belang(wnr, "gebruiker", bsn=nieuwe_gebruiker)
            e = huidig.get("eigenaar")
            if e and e["bsn"] and e["bsn"] not in {p["bsn"] for p in bewoners}:
                self.beeindig_belang(e["id"])  # verkocht
                if nieuwe_gebruiker and self.rng.random() < 0.6:
                    self.belang(wnr, "eigenaar", bsn=nieuwe_gebruiker)
                else:
                    nnp = self.rng.choice(S.CORPORATIES)
                    self.belang(wnr, "eigenaar", nnp=nnp)

    def belang(self, wnr, rol, bsn=None, nnp=None):
        self.cur.execute("INSERT INTO woz.belanghebbende (wozobjectnummer, rol, bsn, nnp_id, nnp_naam, begindatum) "
                         "VALUES (%s, %s, %s, %s, %s, %s)",
                         (wnr, rol, bsn, nnp[0] if nnp else None, nnp[1] if nnp else None, self.dag))

    def beeindig_belang(self, rij_id):
        self.cur.execute("UPDATE woz.belanghebbende SET einddatum = %s, gewijzigd_op = now() WHERE id = %s",
                         (self.dag, rij_id))

    # --- Zaken ---------------------------------------------------------------------

    def zaak(self, zaaktype, bsn=None, nnp=None, obj=None, registratie=None):
        registratie = registratie or self.dag
        self.cur.execute("SELECT coalesce(max(substr(identificatie, 11)::int), 0) + 1 FROM zaken.zaak "
                         "WHERE identificatie LIKE %s", (f"ZAAK-{registratie.year}-%",))
        zid = f"ZAAK-{registratie.year}-{self.cur.fetchone()[0]:06d}"
        self.cur.execute("INSERT INTO zaken.zaak (identificatie, zaaktype_identificatie, initiator_bsn, "
                         "initiator_nnp_id, object_identificatie, registratiedatum) VALUES (%s, %s, %s, %s, %s, %s)",
                         (zid, zaaktype, bsn, nnp, obj, registratie))
        tijd = self.moment() if registratie == self.dag else datetime.combine(registratie, datetime.min.time(), TZ) \
            + timedelta(hours=10)
        self.cur.execute("INSERT INTO zaken.status (zaak_identificatie, statustype, datum_status_gezet) "
                         "VALUES (%s, 'Ontvangen', %s)", (zid, tijd))
        self.teller["zaak"] += 1
        return zid

    def nieuwe_zaak(self, zaaktype):
        if zaaktype == "ZT-WMO":
            kandidaten = [p for p in self.inwoners() if p["leeftijd"] >= 65]
        elif zaaktype == "ZT-KWIJT":
            self.cur.execute("SELECT bsn FROM sociaal.participatiewet_uitkering WHERE einddatum IS NULL ORDER BY bsn")
            bijstand = {r[0] for r in self.cur.fetchall()}
            kandidaten = [p for p in self.volwassenen() if p["bsn"] in bijstand or self.rng.random() < 0.02]
        else:
            kandidaten = self.volwassenen()
        if zaaktype == "ZT-OMV":
            eigen = self.rijen("SELECT b.bsn, b.nnp_id, o.verblijfsobject_identificatie AS vbo FROM woz.belanghebbende b "
                               "JOIN woz.object o USING (wozobjectnummer) WHERE b.rol = 'eigenaar' "
                               "AND b.einddatum IS NULL ORDER BY b.id")
            if not eigen:
                return
            e = self.rng.choice(eigen)
            self.cur.execute("SELECT pand_identificatie FROM bag.verblijfsobject WHERE identificatie = %s", (e["vbo"],))
            self.zaak(zaaktype, e["bsn"], e["nnp_id"], self.cur.fetchone()[0])
            return
        if not kandidaten:
            return
        p = self.rng.choice(kandidaten)
        obj = self.vbo_bij(p["adres"]) if zaaktype in ("ZT-WMO", "ZT-PARK") else None
        self.zaak(zaaktype, p["bsn"], obj=obj)

    def zaken_verder(self):
        """Open zaken schuiven op, binnen kantoortijd: ontvangen -> in behandeling -> afgehandeld."""
        termijn = {zt: dagen for zt, _, dagen in S.ZAAKTYPEN}
        uur_per_dag = 9 * 5 / 7
        for z in self.rijen("""
                SELECT z.identificatie, z.zaaktype_identificatie AS zt, z.initiator_bsn AS bsn,
                       z.object_identificatie AS obj,
                       (SELECT s.statustype FROM zaken.status s WHERE s.zaak_identificatie = z.identificatie
                        ORDER BY s.datum_status_gezet DESC, s.id DESC LIMIT 1) AS status
                FROM zaken.zaak z WHERE z.einddatum IS NULL ORDER BY z.identificatie"""):
            if z["status"] == "Ontvangen":
                if self.rng.random() < 1 / (1.5 * uur_per_dag):
                    self.zaakstatus(z["identificatie"], "In behandeling")
            elif self.rng.random() < 1 / (0.75 * termijn.get(z["zt"], 28) * uur_per_dag):
                self.afhandelen(z)

    def zaakstatus(self, zid, status):
        self.cur.execute("INSERT INTO zaken.status (zaak_identificatie, statustype, datum_status_gezet) "
                         "VALUES (%s, %s, %s)", (zid, status, self.moment()))
        self.cur.execute("UPDATE zaken.zaak SET gewijzigd_op = now() WHERE identificatie = %s", (zid,))

    def afhandelen(self, z):
        uitkomst = self.rng.choices(*zip(*RESULTAAT.get(z["zt"], [("afgehandeld", 1)])))[0]
        self.cur.execute("UPDATE zaken.zaak SET einddatum = %s, resultaat = %s, gewijzigd_op = now() "
                         "WHERE identificatie = %s", (self.dag, uitkomst, z["identificatie"]))
        self.zaakstatus(z["identificatie"], "Afgehandeld")
        self.teller["zaak afgehandeld"] += 1
        if z["zt"] == "ZT-WMO" and uitkomst == "toegekend" and z["bsn"]:
            self.cur.execute("INSERT INTO sociaal.wmo_voorziening (bsn, voorziening, leveringsvorm, startdatum, "
                             "zaak_identificatie) VALUES (%s, %s, %s, %s, %s)",
                             (z["bsn"], S._kies(self.rng, S.WMO),  # pylint: disable=protected-access
                              "PGB" if self.rng.random() < 0.15 else "ZIN",
                              self.dag + timedelta(days=self.rng.randint(7, 21)), z["identificatie"]))
            self.teller["wmo"] += 1
        if z["zt"] == "ZT-KWIJT" and uitkomst == "toegekend" and z["bsn"]:
            self.cur.execute("UPDATE belastingen.aanslag SET status = 'kwijtgescholden', gewijzigd_op = now() "
                             "WHERE subject_bsn = %s AND soort = 'afvalstoffenheffing' AND belastingjaar = %s "
                             "AND status IN ('openstaand', 'aanmaning verstuurd')", (z["bsn"], self.dag.year))

    # --- Meldingen openbare ruimte -------------------------------------------------------

    def melding(self, vbos, volwassenen):
        maand = self.dag.month
        gewichten = [seizoen(sub, maand) for _, sub, _ in MOR]
        hoofd, sub, _ = self.rng.choices(MOR, weights=gewichten)[0]
        v = self.rng.choice(vbos)
        x, y = map(float, re.findall(r"[-\d.]+", v["geometrie_wkt"])[:2])
        self.cur.execute("SELECT coalesce(max(substr(signaalnummer, 5)::int), 0) + 1 FROM mor.melding")
        sid = f"SIG-{self.cur.fetchone()[0]:06d}"
        tijd = self.moment()
        melder = self.rng.choice(volwassenen)["bsn"] if volwassenen and self.rng.random() < 0.35 else None
        self.cur.execute("INSERT INTO mor.melding (signaalnummer, hoofdcategorie, subcategorie, omschrijving, "
                         "nummeraanduiding_identificatie, locatie_wkt, melder_bsn, aangemaakt_op, status) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'gemeld')",
                         (sid, hoofd, sub, f"{sub} (synthetische melding)", v["num"],
                          f"POINT({round(x + self.rng.uniform(-25, 25), 1)} {round(y + self.rng.uniform(-25, 25), 1)})",
                          melder, tijd))
        self.cur.execute("INSERT INTO mor.status (signaalnummer, status, tijdstip) VALUES (%s, 'gemeld', %s)",
                         (sid, tijd))
        self.teller["melding"] += 1

    def meldingen_verder(self):
        dagen = {sub: d for _, sub, d in MOR}
        werktijd = self.t.weekday() < 5 and 7 <= self.t.hour < 18
        for m in self.rijen("SELECT signaalnummer, subcategorie, status FROM mor.melding "
                            "WHERE status <> 'afgehandeld' ORDER BY signaalnummer"):
            if m["status"] == "gemeld" and werktijd and self.rng.random() < 1 / 6:
                nieuw = "in behandeling"
            elif m["status"] == "in behandeling" and self.rng.random() < 1 / (dagen.get(m["subcategorie"], 7) * 0.8 * 24):
                nieuw = "afgehandeld"
            else:
                continue
            tijd = self.moment()
            self.cur.execute("UPDATE mor.melding SET status = %s, afgehandeld_op = %s, gewijzigd_op = now() "
                             "WHERE signaalnummer = %s",
                             (nieuw, tijd if nieuw == "afgehandeld" else None, m["signaalnummer"]))
            self.cur.execute("INSERT INTO mor.status (signaalnummer, status, tijdstip) VALUES (%s, %s, %s)",
                             (m["signaalnummer"], nieuw, tijd))
            self.teller["melding " + nieuw] += 1

    # --- Sociaal domein ------------------------------------------------------------------

    def einde_sociaal(self, bsn, datum):
        for t in ("wmo_voorziening", "jeugdhulp_traject", "participatiewet_uitkering"):
            self.cur.execute(f"UPDATE sociaal.{t} SET einddatum = %s, gewijzigd_op = now() "
                             "WHERE bsn = %s AND (einddatum IS NULL OR einddatum > %s)", (datum, bsn, datum))

    def sociaal_dag(self):
        if self.dag.weekday() >= 5:
            return
        iedereen = self.inwoners()
        for _ in range(poisson(self.rng, TEMPO["jeugdhulp"] * 7 / 5)):
            kinderen = [p for p in iedereen if p["leeftijd"] < 18]
            if kinderen:
                p = self.rng.choice(kinderen)
                self.cur.execute("INSERT INTO sociaal.jeugdhulp_traject (bsn, soort, aanbieder, startdatum) "
                                 "VALUES (%s, %s, %s, %s)", (p["bsn"], S._kies(self.rng, S.JEUGD),  # pylint: disable=protected-access
                                                            self.rng.choice(S.JEUGD_AANBIEDERS), self.dag))
                self.teller["jeugdhulp"] += 1
        self.cur.execute("SELECT bsn FROM sociaal.participatiewet_uitkering WHERE einddatum IS NULL")
        lopend = {r[0] for r in self.cur.fetchall()}
        for _ in range(poisson(self.rng, TEMPO["bijstand"] * 7 / 5)):
            kandidaten = [p for p in iedereen if 21 <= p["leeftijd"] <= 66 and p["bsn"] not in lopend]
            if kandidaten:
                p = self.rng.choice(kandidaten)
                self.cur.execute("INSERT INTO sociaal.participatiewet_uitkering (bsn, regeling, startdatum, maandbedrag) "
                                 "VALUES (%s, 'algemene bijstand', %s, %s)",
                                 (p["bsn"], self.dag, round(self.rng.uniform(1080, 1700), 2)))
                self.teller["bijstand"] += 1
        for tabel, kans in (("wmo_voorziening", 1 / 1200), ("jeugdhulp_traject", 1 / 400),
                            ("participatiewet_uitkering", 1 / 700)):
            for r in self.rijen(f"SELECT id FROM sociaal.{tabel} WHERE einddatum IS NULL AND startdatum <= %s "
                                "ORDER BY id", (self.dag,)):
                if self.rng.random() < kans * 7 / 5:
                    self.cur.execute(f"UPDATE sociaal.{tabel} SET einddatum = %s, gewijzigd_op = now() WHERE id = %s",
                                     (self.dag, r["id"]))
                    self.teller[f"einde {tabel}"] += 1

    # --- BAG: bouwprojecten ----------------------------------------------------------

    def bag_id(self, gemeente, typecode):
        self.cur.execute("SELECT max(identificatie) FROM (SELECT identificatie FROM bag.nummeraanduiding UNION ALL "
                         "SELECT identificatie FROM bag.verblijfsobject UNION ALL SELECT identificatie FROM bag.pand "
                         "UNION ALL SELECT identificatie FROM bag.openbare_ruimte) x WHERE identificatie LIKE %s",
                         (f"{gemeente}{typecode}9%",))
        hoogste = self.cur.fetchone()[0]
        return f"{gemeente}{typecode}{(int(hoogste[6:]) if hoogste else 9000000000) + 1:010d}"

    def bouwproject(self):
        kandidaten = self.rijen("""SELECT w.identificatie, w.gemeentecode, count(*) AS n FROM bag.woonplaats w
            JOIN bag.openbare_ruimte o ON o.woonplaats_identificatie = w.identificatie
            WHERE w.gemeentecode = ANY(%s) GROUP BY 1, 2 ORDER BY n DESC, 1 LIMIT 4""", (sorted(I.KERNGEMEENTEN),))
        if not kandidaten:
            return
        wp = self.rng.choice(kandidaten)
        gem = wp["gemeentecode"]
        self.cur.execute("SELECT naam FROM bag.openbare_ruimte WHERE woonplaats_identificatie = %s",
                         (wp["identificatie"],))
        bestaand = {r[0] for r in self.cur.fetchall()}
        vrij = [s for s in NIEUWE_STRATEN if s not in bestaand]
        if not vrij:
            return
        straat = self.rng.choice(vrij)
        self.cur.execute("SELECT n.postcode FROM bag.nummeraanduiding n JOIN bag.openbare_ruimte o "
                         "ON o.identificatie = n.openbare_ruimte_identificatie WHERE o.woonplaats_identificatie = %s "
                         "AND n.postcode IS NOT NULL ORDER BY 1 LIMIT 1", (wp["identificatie"],))
        r = self.cur.fetchone()
        postcode = (r[0][:4] if r else "9999") + self.rng.choice("WXYZ") + self.rng.choice("ABCDEFGHJKLMNPRSTV")
        or_id = self.bag_id(gem, "30")
        self.cur.execute("INSERT INTO bag.openbare_ruimte (identificatie, naam, type, woonplaats_identificatie, status) "
                         "VALUES (%s, %s, 'Weg', %s, 'Naamgeving uitgegeven')", (or_id, straat, wp["identificatie"]))
        cx, cy = S.MIDDELPUNT.get(gem, (155000, 463000))
        x, y = cx + self.rng.uniform(-3000, 3000), cy + self.rng.uniform(-3000, 3000)
        start = self.dag + timedelta(days=self.rng.randint(14, 45))
        gereed = start + timedelta(days=self.rng.randint(120, 240))
        pand = self.bag_id(gem, "10")
        self.cur.execute("INSERT INTO bag.pand (identificatie, oorspronkelijk_bouwjaar, status, geometrie_wkt) "
                         "VALUES (%s, %s, 'Bouwvergunning verleend', %s)",
                         (pand, gereed.year, f"POLYGON(({x-20:.1f} {y-12:.1f},{x+20:.1f} {y-12:.1f},{x+20:.1f} "
                                             f"{y+12:.1f},{x-20:.1f} {y+12:.1f},{x-20:.1f} {y-12:.1f}))"))
        n = self.rng.randint(8, 30)
        for nr in range(1, n + 1):
            num, vbo = self.bag_id(gem, "20"), None
            self.cur.execute("INSERT INTO bag.nummeraanduiding (identificatie, huisnummer, postcode, "
                             "type_adresseerbaar_object, openbare_ruimte_identificatie, status) "
                             "VALUES (%s, %s, %s, 'Verblijfsobject', %s, 'Naamgeving uitgegeven')",
                             (num, nr, postcode, or_id))
            vbo = self.bag_id(gem, "01")
            self.cur.execute("INSERT INTO bag.verblijfsobject (identificatie, hoofdadres_identificatie, "
                             "pand_identificatie, gebruiksdoel, oppervlakte, status, geometrie_wkt) "
                             "VALUES (%s, %s, %s, 'woonfunctie', %s, 'Verblijfsobject gevormd', %s)",
                             (vbo, num, pand, self.rng.randint(50, 115),
                              f"POINT({x + self.rng.uniform(-15, 15):.1f} {y + self.rng.uniform(-8, 8):.1f})"))
        self.cur.execute("INSERT INTO sim.bouwproject (pand, gemeente, start, gereed, fase) "
                         "VALUES (%s, %s, %s, %s, 'vergunning')", (pand, gem, start, gereed))
        nnp = self.rng.choice(S.CORPORATIES)
        zid = self.zaak("ZT-OMV", nnp=nnp[0], obj=pand, registratie=self.dag - timedelta(days=self.rng.randint(50, 90)))
        self.afhandelen(dict(identificatie=zid, zt="ZT-OMV-project", bsn=None))
        self.cur.execute("UPDATE zaken.zaak SET resultaat = 'verleend' WHERE identificatie = %s", (zid,))
        self.log("bouwproject", f"{n} woningen aan de {straat} ({gem}), start {start}, gereed {gereed}")

    def bouw_dag(self):
        for p in self.rijen("SELECT * FROM sim.bouwproject WHERE fase <> 'ingemeten' ORDER BY pand"):
            if p["fase"] == "vergunning" and self.dag >= p["start"]:
                self.pandstatus(p["pand"], "Bouw gestart", None, "bouw")
            elif p["fase"] == "bouw" and self.dag >= p["gereed"]:
                self.pandstatus(p["pand"], "Pand in gebruik (niet ingemeten)",
                                "Verblijfsobject in gebruik (niet ingemeten)", "gereed")
                self.woz_nieuw(p["pand"], p["gemeente"])
                self.log("oplevering", f"pand {p['pand']} in gebruik")
            elif p["fase"] == "gereed" and self.dag >= p["gereed"] + timedelta(days=60):
                self.pandstatus(p["pand"], "Pand in gebruik", WOON, "ingemeten")

    def pandstatus(self, pand, status, vbo_status, fase):
        self.cur.execute("UPDATE bag.pand SET status = %s, gewijzigd_op = now() WHERE identificatie = %s", (status, pand))
        if vbo_status:
            self.cur.execute("UPDATE bag.verblijfsobject SET status = %s, gewijzigd_op = now() "
                             "WHERE pand_identificatie = %s", (vbo_status, pand))
        self.cur.execute("UPDATE sim.bouwproject SET fase = %s WHERE pand = %s", (fase, pand))

    def woz_nieuw(self, pand, gemeente):
        self.cur.execute("SELECT max(waardepeildatum) FROM woz.waarde")
        peil = self.cur.fetchone()[0]
        self.cur.execute("SELECT max(wozobjectnummer) FROM woz.object WHERE gemeentecode = %s", (gemeente,))
        hoogste = self.cur.fetchone()[0]
        volg = int(hoogste[4:]) if hoogste else 0
        nnp = self.rng.choice(S.CORPORATIES)
        for r in self.rijen("SELECT identificatie, oppervlakte FROM bag.verblijfsobject "
                            "WHERE pand_identificatie = %s ORDER BY 1", (pand,)):
            vbo, opp = r["identificatie"], r["oppervlakte"]
            volg += 1
            wnr = f"{gemeente}{volg:08d}"
            self.cur.execute("INSERT INTO woz.object (wozobjectnummer, verblijfsobject_identificatie, soort_object, "
                             "gemeentecode) VALUES (%s, %s, 'woning', %s)", (wnr, vbo, gemeente))
            waarde = int(round(opp * S.M2_PRIJS.get(gemeente, 3400) * 1.25 * self.rng.uniform(0.9, 1.1), -3))
            self.cur.execute("INSERT INTO woz.waarde (wozobjectnummer, waardepeildatum, vastgestelde_waarde) "
                             "VALUES (%s, %s, %s)", (wnr, peil, waarde))
            self.belang(wnr, "eigenaar", nnp=nnp)

    # --- Jaarlijks en dagelijks: WOZ en belastingen ---------------------------------------

    def woz_jaar(self):
        peil = date(self.dag.year - 1, 1, 1)
        self.cur.execute("SELECT 1 FROM woz.waarde WHERE waardepeildatum = %s LIMIT 1", (peil,))
        if self.cur.fetchone():
            return
        groei = 1.055
        rijen = self.rijen("SELECT DISTINCT ON (wozobjectnummer) wozobjectnummer, vastgestelde_waarde FROM woz.waarde "
                           "WHERE waardepeildatum < %s ORDER BY wozobjectnummer, waardepeildatum DESC", (peil,))
        self.cur.executemany(
            "INSERT INTO woz.waarde (wozobjectnummer, waardepeildatum, vastgestelde_waarde) VALUES (%s, %s, %s)",
            [(r["wozobjectnummer"], peil, int(round(r["vastgestelde_waarde"] * groei * self.rng.uniform(0.96, 1.04), -3)))
             for r in rijen])
        self.log("woz", f"{len(rijen)} nieuwe WOZ-waarden, peildatum {peil}")

    def aanslagen_jaar(self):
        jaar = self.dag.year
        self.cur.execute("SELECT 1 FROM belastingen.aanslag WHERE belastingjaar = %s LIMIT 1", (jaar,))
        if self.cur.fetchone():
            return
        peil = date(jaar - 1, 1, 1)
        objecten = self.rijen("""
            SELECT o.wozobjectnummer, o.verblijfsobject_identificatie AS vbo, o.soort_object, w.vastgestelde_waarde,
                   n.postcode, n.huisnummer::text AS huisnummer, coalesce(n.huisletter, '') AS letter,
                   coalesce(n.huisnummertoevoeging, '') AS toev,
                   (SELECT row(b.bsn, b.nnp_id)::text FROM woz.belanghebbende b WHERE b.wozobjectnummer = o.wozobjectnummer
                      AND b.rol = 'eigenaar' AND b.einddatum IS NULL ORDER BY b.id DESC LIMIT 1) AS eigenaar,
                   (SELECT b.bsn FROM woz.belanghebbende b WHERE b.wozobjectnummer = o.wozobjectnummer
                      AND b.rol = 'gebruiker' AND b.einddatum IS NULL ORDER BY b.id DESC LIMIT 1) AS gebruiker
            FROM woz.object o
            JOIN woz.waarde w ON w.wozobjectnummer = o.wozobjectnummer AND w.waardepeildatum = %s
            JOIN bag.verblijfsobject v ON v.identificatie = o.verblijfsobject_identificatie
            JOIN bag.nummeraanduiding n ON n.identificatie = v.hoofdadres_identificatie
            WHERE v.status LIKE %s ORDER BY o.wozobjectnummer""", (peil, WOON + "%"))
        per_adres = collections.Counter(p["adres"] for p in self.inwoners())
        self.cur.execute("SELECT bsn FROM sociaal.participatiewet_uitkering WHERE einddatum IS NULL")
        bijstand = {r[0] for r in self.cur.fetchall()}
        nr, rijen = 0, []
        for o in objecten:
            woning = o["soort_object"] == "woning"
            if o["eigenaar"]:
                bsn, nnp = (x or None for x in o["eigenaar"].strip("()").split(","))
                nr += 1
                rijen.append((f"{jaar}{nr:08d}", jaar, "OZB eigenaren", bsn, nnp, o["wozobjectnummer"],
                              round(o["vastgestelde_waarde"] * (0.00046 if woning else 0.00113), 2), "openstaand"))
            if woning and o["gebruiker"]:
                bewoners = per_adres[(o["postcode"], o["huisnummer"], o["letter"], o["toev"])]
                nr += 1
                rijen.append((f"{jaar}{nr:08d}", jaar, "afvalstoffenheffing", o["gebruiker"], None,
                              o["wozobjectnummer"], round((295 if bewoners <= 1 else 380) * 1.03 ** (jaar - 2027), 2),
                              "kwijtgescholden" if o["gebruiker"] in bijstand else "openstaand"))
        self.cur.executemany("INSERT INTO belastingen.aanslag (aanslagnummer, belastingjaar, soort, subject_bsn, "
                             "subject_nnp_id, wozobjectnummer, bedrag, dagtekening, status) "
                             f"VALUES (%s, %s, %s, %s, %s, %s, %s, '{self.dag}', %s)", rijen)
        self.log("aanslagen", f"{len(rijen)} aanslagen {jaar} verstuurd")

    def betalingen_dag(self):
        for a in self.rijen("SELECT id, dagtekening, status FROM belastingen.aanslag "
                            "WHERE status IN ('openstaand', 'aanmaning verstuurd') ORDER BY id"):
            dagen = (self.dag - a["dagtekening"]).days
            nieuw = None
            if a["status"] == "openstaand" and dagen < 45 and self.rng.random() < 0.08:
                nieuw = "betaald"
            elif a["status"] == "openstaand" and dagen >= 45:
                nieuw = "aanmaning verstuurd"
            elif a["status"] == "aanmaning verstuurd" and self.rng.random() < 0.03:
                nieuw = "betaald"
            if nieuw:
                self.cur.execute("UPDATE belastingen.aanslag SET status = %s, gewijzigd_op = now() WHERE id = %s",
                                 (nieuw, a["id"]))
                self.teller["aanslag " + nieuw] += 1

    # --- Eén uur ---------------------------------------------------------------------------

    def draai(self):
        t, maand = self.t, self.t.month
        if t.hour == 6:  # dagelijks, vroeg
            if self.dag.month == 1 and self.dag.day == 1:
                self.woz_jaar()
            if self.dag == laatste_werkdag_februari(self.dag.year):
                self.aanslagen_jaar()
            self.betalingen_dag()
            self.bouw_dag()
            if self.rng.random() < TEMPO["bouwproject"]:
                self.bouwproject()
        if t.hour == 10:
            self.sociaal_dag()
        w = kantoor(t)
        for soort in ("geboorte", "overlijden", "verhuizing", "vestiging", "vertrek"):
            for _ in range(poisson(self.rng, TEMPO[soort] * w)):
                getattr(self, soort)()
        for zt in ("ZT-PARK", "ZT-UITT", "ZT-OMV", "ZT-EVEN", "ZT-WMO", "ZT-KWIJT"):
            for _ in range(poisson(self.rng, TEMPO[zt] * w * seizoen(zt, maand))):
                self.nieuwe_zaak(zt)
        n = poisson(self.rng, TEMPO["melding"] * BURGER[t.hour])
        if n:
            vbos = self.rijen("SELECT v.identificatie, n.identificatie AS num, v.geometrie_wkt FROM bag.verblijfsobject v "
                              "JOIN bag.nummeraanduiding n ON n.identificatie = v.hoofdadres_identificatie "
                              "ORDER BY v.identificatie")
            volwassenen = self.volwassenen()
            for _ in range(n):
                self.melding(vbos, volwassenen)
        self.meldingen_verder()
        if w:
            self.zaken_verder()


def laatste_werkdag_februari(jaar):
    d = date(jaar, 3, 1) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def zet_klaar(cur):
    """Na het (opnieuw) maken van de synthetische bronnen: de klok terug naar het begin."""
    cur.execute(SQL)
    cur.execute("TRUNCATE sim.logboek, sim.bouwproject, sim.export RESTART IDENTITY")
    cur.execute("INSERT INTO sim.voortgang (id, tot) VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET tot = EXCLUDED.tot",
                (START,))


def simuleer(con, tot=None):
    nu = datetime.now(timezone.utc) if tot is None else datetime.fromisoformat(tot).replace(tzinfo=TZ)
    nu = min(nu, EIND).astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with con.cursor() as cur:
        cur.execute("SELECT to_regclass('bag.verblijfsobject'), to_regclass('sim.voortgang')")
        if None in cur.fetchone():
            raise SystemExit("Eerst: bron.sh synthetisch")
        cur.execute(SQL)
        cur.execute("SELECT tot FROM sim.voortgang WHERE id = 1")
        rij = cur.fetchone()
        t = (rij[0] if rij else START).astimezone(timezone.utc)
    con.commit()
    totaal, uren = collections.Counter(), 0
    while t < nu:
        with con.cursor() as cur:
            uur = Uur(cur, t.astimezone(TZ))
            uur.draai()
            t += timedelta(hours=1)
            cur.execute("UPDATE sim.voortgang SET tot = %s WHERE id = 1", (t,))
        con.commit()
        totaal.update(uur.teller)
        uren += 1
    if not uren:
        print(f"De klok staat al op {t.astimezone(TZ):%d-%m-%Y %H:%M}" +
              (" (einde van de simulatie)" if t >= EIND else ""))
        return
    print(f"Gesimuleerd: {uren} uur, tot {t.astimezone(TZ):%d-%m-%Y %H:%M}")
    for k, n in sorted(totaal.items()):
        print(f"  {k:36} {n:6}")


def status(con):
    with con.cursor() as cur:
        cur.execute("SELECT to_regclass('sim.voortgang')")
        if cur.fetchone()[0] is None:
            print("De simulatie is nog niet ingericht (bron.sh synthetisch).")
            return
        cur.execute("SELECT tot FROM sim.voortgang WHERE id = 1")
        tot = cur.fetchone()[0]
        print(f"Simulatieklok: {tot.astimezone(TZ):%d-%m-%Y %H:%M} (loopt van {START:%d-%m-%Y} tot {EIND:%d-%m-%Y})")
        cur.execute("SELECT tijdstip, soort, tekst FROM sim.logboek ORDER BY tijdstip DESC, id DESC LIMIT 15")
        for tijd, soort, tekst in cur.fetchall():
            print(f"  {tijd.astimezone(TZ):%d-%m %H:%M}  {soort:12} {tekst}")
        cur.execute("""SELECT
            (SELECT count(*) FROM brp.persoonslijst),
            (SELECT count(*) FROM mor.melding WHERE status <> 'afgehandeld'),
            (SELECT count(*) FROM zaken.zaak WHERE einddatum IS NULL),
            (SELECT count(*) FROM sim.bouwproject WHERE fase <> 'ingemeten')""")
        pl, mor, zk, bouw = cur.fetchone()
        print(f"Persoonslijsten {pl}, open meldingen {mor}, open zaken {zk}, lopende bouwprojecten {bouw}")
