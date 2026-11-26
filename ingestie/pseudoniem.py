"""Pseudonimiseren bij de poort, met een sleutelkluis (DF-ADR-015).

Een BSN komt nooit in het lakehouse. Bij de ingestie wordt het vervangen door
een pseudoniem: een willekeurige UUID per persoon. De koppeling staat alleen in
de kluis, een eigen database op dfc, en daar alleen als HMAC van het BSN:

    kluis.koppeling  (bsn_hmac, pseudoniem, aangemaakt, vernietigd, verzoek)
    kluis.blokkade   (bron, sleutel, verzoek, sinds)

Namen en A-nummers (direct identificerend) laten we weg. Wat blijft
(geboortedatum, adres, de technische pl_id) is indirect identificerend; dat
risico staat in DF-ADR-015.

Verwijderen (crypto-shredding): de job verwijderen zet het pseudoniem in de
kluis op NULL. Daarna is het pseudoniem in het lakehouse niet meer naar een BSN
te herleiden, ook niet door wie de kluissleutel heeft, want het pseudoniem is
willekeurig en niet afgeleid. Een BSN met een vernietigde koppeling krijgt bij
een volgende ingestie geen nieuw pseudoniem: persoonsgebonden rijen worden
overgeslagen, andere rijen krijgen een leeg pseudoniem. De BRP-rijen van de
persoon (via pl_id) staan op de blokkadelijst.

De HMAC komt van OpenBao op dfw (transit, sleutel kluis-bsn): de sleutel
verlaat OpenBao nooit, en elke vraag staat in het auditlog daar. De database
met de koppelingen staat op dfc. Wie dfc binnendringt, heeft dus pseudoniemen
en HMAC's, maar niet de sleutel om een BSN te herleiden.

Configuratie: KLUIS_BAO_ADRES en KLUIS_BAO_TOKEN (OpenBao), KLUIS_DSN (de
database). Alleen voor tests en lokaal: KLUIS_GEHEIM (een HMAC-sleutel in het
proces) in plaats van OpenBao, en zonder KLUIS_DSN een kluis in het geheugen.
"""

import base64

import hashlib
import hmac
import os
import uuid

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS kluis;
CREATE TABLE IF NOT EXISTS kluis.koppeling (
  bsn_hmac    bytea PRIMARY KEY,
  pseudoniem  uuid UNIQUE,
  aangemaakt  timestamptz NOT NULL DEFAULT now(),
  vernietigd  timestamptz,
  verzoek     uuid,
  CHECK ((vernietigd IS NULL) = (pseudoniem IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS kluis.blokkade (
  bron     text NOT NULL,
  sleutel  text NOT NULL,
  verzoek  uuid,
  sinds    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (bron, sleutel)
);
"""

# Per bron en tabel: welke kolom een BSN bevat (en hoe het pseudoniem heet),
# welke kolommen weg moeten, en of een rij helemaal over de persoon gaat.
BRP_WEG = ["a_nummer", "vorig_a_nummer", "volgend_a_nummer", "voornamen", "voorvoegsel_geslachtsnaam",
           "geslachtsnaam", "adellijke_titel_predikaat"]
REGELS = {
    "brp": {
        "*": {"bsn": {"burgerservicenummer": "pseudoniem"}, "weg": BRP_WEG, "blokkeer_op": "pl_id"},
        "persoonslijst": {"bsn": {"burgerservicenummer": "pseudoniem"}, "weg": ["a_nummer"], "blokkeer_op": "id"},
        "codetabel": None,
    },
    "woz": {"belanghebbende": {"bsn": {"bsn": "pseudoniem"}}},
    "mor": {"melding": {"bsn": {"melder_bsn": "melder_pseudoniem"}}},
    "sociaal": {
        "wmo_voorziening": {"bsn": {"bsn": "pseudoniem"}, "persoonsgebonden": True},
        "jeugdhulp_traject": {"bsn": {"bsn": "pseudoniem"}, "persoonsgebonden": True},
        "participatiewet_uitkering": {"bsn": {"bsn": "pseudoniem"}, "persoonsgebonden": True},
    },
    "belastingen": {"aanslag": {"bsn": {"bsn": "pseudoniem"}}},
    "zaken": {"rollen": {"genest": ("betrokkene_identificatie", "inp_bsn")}},
}


def hmac_bsn(bsn, geheim):
    """HMAC in het proces; alleen voor tests en lokaal (portaal/backend/src/kluis.ts doet hetzelfde)."""
    return hmac.new(geheim.encode(), f"bsn:{bsn}".encode(), hashlib.sha256).digest()


class KluisVerzegeld(RuntimeError):
    pass


class OpenBao:
    """De HMAC van een BSN, berekend door OpenBao (transit/hmac/kluis-bsn)."""

    def __init__(self, adres, token):
        import requests  # pylint: disable=import-outside-toplevel
        self.adres, self.s = adres.rstrip("/"), requests.Session()
        self.s.headers["X-Vault-Token"] = token
        # Het token is periodiek: elke keer verlengen houdt het in leven.
        try:
            self.s.post(f"{self.adres}/v1/auth/token/renew-self", timeout=5)
        except Exception:  # pylint: disable=broad-except
            pass

    def hmac(self, tekst):
        r = self.s.post(f"{self.adres}/v1/transit/hmac/kluis-bsn/sha2-256",
                        json={"input": base64.b64encode(tekst.encode()).decode()}, timeout=10)
        if r.status_code == 503:
            raise KluisVerzegeld("De kluis (OpenBao op dfw) is verzegeld. Op dfw: sudo ./bron.sh kluis-ontzegel")
        r.raise_for_status()
        return base64.b64decode(r.json()["data"]["hmac"].split(":", 2)[2])


class Kluis:
    def __init__(self, dsn=None, geheim=None, bao=None):
        self.bao = bao
        if self.bao is None and os.environ.get("KLUIS_BAO_ADRES"):
            self.bao = OpenBao(os.environ["KLUIS_BAO_ADRES"], os.environ["KLUIS_BAO_TOKEN"])
        self.geheim = geheim or os.environ.get("KLUIS_GEHEIM")
        if not self.bao and not self.geheim:
            raise RuntimeError("Geen kluis: zet KLUIS_BAO_ADRES en KLUIS_BAO_TOKEN (of, alleen lokaal, KLUIS_GEHEIM)")
        self.dsn = dsn if dsn is not None else os.environ.get("KLUIS_DSN")
        self.cache = {}
        self.geheugen = {} if not self.dsn else None
        self.con = None
        if self.dsn:
            import psycopg2  # pylint: disable=import-outside-toplevel
            self.con = psycopg2.connect(self.dsn)
            with self.con.cursor() as cur:
                cur.execute(SCHEMA)
            self.con.commit()

    def pseudoniem(self, bsn):
        """Het pseudoniem van een BSN; een nieuw als het er nog niet is. None: geen BSN, of vernietigd."""
        if not bsn or not str(bsn).strip("0 "):
            return None
        bsn = str(bsn).strip().zfill(9)
        if bsn in self.cache:
            return self.cache[bsn]
        h = self.hmac(bsn)
        if self.geheugen is not None:
            p = self.geheugen.setdefault(h, str(uuid.uuid4()))
        else:
            with self.con.cursor() as cur:
                cur.execute("INSERT INTO kluis.koppeling (bsn_hmac, pseudoniem) VALUES (%s, %s) "
                            "ON CONFLICT (bsn_hmac) DO NOTHING", (h, str(uuid.uuid4())))
                cur.execute("SELECT pseudoniem FROM kluis.koppeling WHERE bsn_hmac = %s", (h,))
                p = cur.fetchone()[0]
            self.con.commit()
            p = str(p) if p else None
        self.cache[bsn] = p
        return p

    def hmac(self, bsn):
        return self.bao.hmac(f"bsn:{bsn}") if self.bao else hmac_bsn(bsn, self.geheim)

    def blokkades(self, bron):
        if self.geheugen is not None:
            return set()
        with self.con.cursor() as cur:
            cur.execute("SELECT sleutel FROM kluis.blokkade WHERE bron = %s", (bron,))
            return {r[0] for r in cur.fetchall()}

    def vernietig(self, bsn_hmac, verzoek):
        """Crypto-shredding: het pseudoniem weg; de HMAC blijft als blokkade. Geeft het oude pseudoniem."""
        with self.con.cursor() as cur:
            cur.execute("SELECT pseudoniem FROM kluis.koppeling WHERE bsn_hmac = %s FOR UPDATE", (bsn_hmac,))
            rij = cur.fetchone()
            if rij is None:
                cur.execute("INSERT INTO kluis.koppeling (bsn_hmac, pseudoniem, vernietigd, verzoek) "
                            "VALUES (%s, NULL, now(), %s)", (bsn_hmac, verzoek))
                oud = None
            else:
                oud = str(rij[0]) if rij[0] else None
                cur.execute("UPDATE kluis.koppeling SET pseudoniem = NULL, vernietigd = coalesce(vernietigd, now()), "
                            "verzoek = coalesce(verzoek, %s) WHERE bsn_hmac = %s", (verzoek, bsn_hmac))
        return oud

    def blokkeer(self, bron, sleutels, verzoek):
        with self.con.cursor() as cur:
            for s in sleutels:
                cur.execute("INSERT INTO kluis.blokkade (bron, sleutel, verzoek) VALUES (%s, %s, %s) "
                            "ON CONFLICT DO NOTHING", (bron, str(s), verzoek))

    def bevestig(self):
        self.con.commit()


def regels(bron, tabel):
    r = REGELS.get(bron)
    if not r:
        return None
    if tabel in r:
        return r[tabel]
    return r.get("*")


def pseudonimiseer(bron, tabel, kluis=None):
    """Een functie voor dlt (add_map / add_filter): BSN eruit, pseudoniem erin.
    Geeft None als de tabel niets met personen te maken heeft."""
    r = regels(bron, tabel)
    if not r:
        return None
    k = kluis or Kluis()
    blokkade = k.blokkades(bron) if r.get("blokkeer_op") else set()

    def rij(item):
        if r.get("blokkeer_op") and str(item.get(r["blokkeer_op"])) in blokkade:
            return None
        for weg in r.get("weg", []):
            item.pop(weg, None)
        for kolom, nieuw in r.get("bsn", {}).items():
            # Uit de database komt het BSN al onder de nieuwe naam (zie query_adapter); uit een API of bestand niet.
            if kolom in item or nieuw in item:
                bsn = item.pop(kolom) if kolom in item else item.get(nieuw)
                p = k.pseudoniem(bsn)
                if bsn and p is None and r.get("persoonsgebonden"):
                    return None  # vernietigd: de rij gaat over die persoon
                item[nieuw] = p
        if "genest" in r:
            veld, sub = r["genest"]
            for sleutel in (veld, "betrokkeneIdentificatie"):
                genest = item.get(sleutel)
                if isinstance(genest, dict):
                    for s in (sub, "inpBsn"):
                        if s in genest:
                            genest["pseudoniem"] = k.pseudoniem(genest.pop(s))
        return item

    return rij


# --- Voor sql_database: de kolommen al bij het lezen aanpassen -----------------------
# Namen en A-nummers worden niet eens gelezen. Het BSN wordt gelezen onder de naam
# van het pseudoniem, zodat er in het schema van dlt nooit een kolom met een BSN staat;
# de map hierboven vervangt de waarde voordat er iets wordt weggeschreven.

def tabel_adapter(bron):
    import sqlalchemy as sa  # pylint: disable=import-outside-toplevel

    def adapter(tabel):
        r = regels(bron, tabel.name)
        if not r:
            return tabel
        for weg in r.get("weg", []):
            if weg in tabel.c:
                tabel._columns.remove(tabel.c[weg])  # pylint: disable=protected-access
        for kolom, nieuw in r.get("bsn", {}).items():
            if kolom in tabel.c:
                tabel._columns.remove(tabel.c[kolom])  # pylint: disable=protected-access
                tabel.append_column(sa.Column(nieuw, sa.Text, nullable=True), replace_existing=True)
        return tabel

    return adapter


def query_adapter(bron):
    import sqlalchemy as sa  # pylint: disable=import-outside-toplevel

    def adapter(query, tabel, *_):
        r = regels(bron, tabel.name)
        if not r or not r.get("bsn"):
            return query
        terug = {nieuw: kolom for kolom, nieuw in r["bsn"].items()}
        kolommen = [sa.literal_column(f'"{terug[c.name]}"', sa.Text).label(c.name) if c.name in terug else c
                    for c in tabel.columns]
        return query.with_only_columns(*kolommen)

    return adapter
