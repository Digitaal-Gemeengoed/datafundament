"""Echte CDC: de logische replicatie van PostgreSQL lezen (DF-ADR-006).

Elke laag van een databasebron heeft een eigen replicatieslot op de bron,
`df_<laag>` (bijvoorbeeld df_ruw_bag en df_ruw_bag_stand), op de publicatie
`df_<bron>`. Zo leest elke laag alle wijzigingen, los van de andere laag.

Het verloop van één lading:

  1. Is er nog geen slot, dan maken we het aan en laden we nog één keer
     incrementeel op gewijzigd_op (bronnen.laad_incrementeel). Wat in de
     tussentijd wijzigt, komt via het slot nog een keer: at-least-once.
  2. Daarna kijken we in het slot (pg_logical_slot_peek_binary_changes), in
     porties van hele transacties, en decoderen de berichten van pgoutput.
  3. dlt schrijft de portie weg, gepseudonimiseerd zoals altijd:
       ruw_<bron>        elke wijziging, ook verwijderingen, met _cdc_bewerking
                         (I, U, D), _cdc_lsn en _cdc_tijdstip (de commit)
       ruw_<bron>_stand  upsert van de laatste versie per id; wat verwijderd is,
                         gaat eruit (Iceberg-delete)
  4. Pas als dat gelukt is, schuiven we het slot op (pg_replication_slot_advance).
     Gaat er iets mis, dan komt dezelfde portie de volgende keer opnieuw.

De publicatie op de bron noemt per tabel de kolommen (bron/werkbank/publicaties.py):
namen en A-nummers zitten er niet in en gaan dus nooit over de lijn. Een nieuwe
kolom komt pas door als de publicatie is bijgewerkt (bron.sh publicaties).
TRUNCATE wordt niet gepubliceerd; na het opnieuw vullen van een bron hoort
beheer.opnieuw_laden, dat ook de slots weggooit.
"""

import datetime as dt
import struct

import dlt

PORTIE = 20_000  # wijzigingen per keer; pgoutput stopt pas aan het eind van een transactie
EPOCH = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)


# De kolommen van CDC, ook al bij de inhaalslag, zodat dbt erop kan rekenen.
KOLOMMEN = [
    {"name": "_cdc_bewerking", "data_type": "text", "nullable": True},
    {"name": "_cdc_lsn", "data_type": "text", "nullable": True},
    {"name": "_cdc_tijdstip", "data_type": "timestamp", "nullable": True},
]


def slot(laag):
    return f"df_{laag}"


def publicatie(bron):
    return f"df_{bron}"


# --- pgoutput (protocolversie 1) ---------------------------------------------------

class Lezer:
    def __init__(self, data):
        self.d, self.p = bytes(data), 0

    def neem(self, fmt):
        w = struct.unpack_from("!" + fmt, self.d, self.p)
        self.p += struct.calcsize("!" + fmt)
        return w if len(w) > 1 else w[0]

    def tekst(self):
        eind = self.d.index(b"\0", self.p)
        s = self.d[self.p:eind].decode()
        self.p = eind + 1
        return s

    def tupel(self):
        n = self.neem("h")
        uit = []
        for _ in range(n):
            soort = self.neem("c")
            if soort == b"t":
                lengte = self.neem("i")
                uit.append(("t", self.d[self.p:self.p + lengte].decode()))
                self.p += lengte
            else:
                uit.append((soort.decode(), None))  # n: NULL, u: ongewijzigde TOAST-waarde
        return uit


def lsn_tekst(lsn):
    return f"{lsn >> 32:X}/{lsn & 0xFFFFFFFF:X}"


class Decoder:
    """Zet de berichten van pgoutput om in wijzigingen: dicts per tabel.

    Waarden komen als tekst; omzetten doen we met de typecasters van psycopg2,
    dezelfde als bij het incrementeel lezen, zodat de typen in dlt gelijk blijven."""

    def __init__(self, omzetten):
        self.omzetten = omzetten  # (type-oid, tekst) -> Python-waarde
        self.relaties = {}
        self.commit = None
        self.wijzigingen = []  # in de huidige transactie
        self.toast = 0
        self.eind = None  # de eind-LSN van de laatste commit

    def rij(self, relid, tupel):
        schema, tabel, kolommen = self.relaties[relid]
        uit = {}
        for (naam, oid), (soort, waarde) in zip(kolommen, tupel):
            if soort == "u":
                self.toast += 1
                continue
            uit[naam] = None if soort == "n" else self.omzetten(oid, waarde)
        return schema, tabel, uit

    def bericht(self, data):
        """Eén bericht; geeft de wijzigingen van een transactie terug bij de commit."""
        r = Lezer(data)
        soort = r.neem("c")
        if soort == b"B":
            _, tijd, _ = r.neem("qqi")
            self.commit = EPOCH + dt.timedelta(microseconds=tijd)
            self.wijzigingen = []
        elif soort == b"R":
            relid = r.neem("I")
            schema, tabel = r.tekst(), r.tekst()
            r.neem("b")  # replica identity
            kolommen = []
            for _ in range(r.neem("h")):
                r.neem("b")
                naam = r.tekst()
                oid, _ = r.neem("Ii")
                kolommen.append((naam, oid))
            self.relaties[relid] = (schema, tabel, kolommen)
        elif soort == b"I":
            relid = r.neem("I")
            assert r.neem("c") == b"N"
            self.wijzigingen.append(("I", *self.rij(relid, r.tupel())))
        elif soort == b"U":
            relid = r.neem("I")
            soort_tupel = r.neem("c")
            if soort_tupel in (b"K", b"O"):  # de oude sleutel, alleen als die wijzigde
                r.tupel()
                soort_tupel = r.neem("c")
            assert soort_tupel == b"N"
            self.wijzigingen.append(("U", *self.rij(relid, r.tupel())))
        elif soort == b"D":
            relid = r.neem("I")
            assert r.neem("c") in (b"K", b"O")
            schema, tabel, rij = self.rij(relid, r.tupel())
            self.wijzigingen.append(("D", schema, tabel, rij))
        elif soort == b"C":
            _, _, eind, _ = r.neem("bqqq")
            self.eind = eind
            klaar = [(b, s, t, rij, self.commit, eind) for b, s, t, rij in self.wijzigingen]
            self.wijzigingen = []
            return klaar
        # Y (type), O (oorsprong), M (bericht), T (truncate, niet gepubliceerd): niets mee
        return []


def psycopg2_omzetter(cur):
    import psycopg2.extensions as ext  # pylint: disable=import-outside-toplevel
    cache = {}

    def omzet(oid, tekst):
        if oid not in cache:
            cache[oid] = ext.string_types.get(oid)
        f = cache[oid]
        return f(tekst, cur) if f else tekst

    return omzet


# --- Het slot ------------------------------------------------------------------------

class Slot:
    def __init__(self, con, naam, pub):
        self.con, self.naam, self.pub = con, naam, pub
        self.verloren = False

    def bestaat(self):
        """Bestaat het slot? Een slot dat te ver achterliep (max_slot_wal_keep_size) is
        onbruikbaar: dat gooien we weg, en dan begint het opnieuw met een inhaalslag."""
        with self.con.cursor() as cur:
            cur.execute("SELECT wal_status FROM pg_replication_slots WHERE slot_name = %s", (self.naam,))
            rij = cur.fetchone()
        if rij and rij[0] == "lost":
            self.verloren = True
            self.weg()
            return False
        return rij is not None

    def maak(self):
        with self.con.cursor() as cur:
            cur.execute("SELECT pg_create_logical_replication_slot(%s, 'pgoutput')", (self.naam,))
        self.con.commit()

    def kijk(self, aantal=PORTIE):
        """Hele transacties uit het slot, zonder het op te schuiven. Geeft (wijzigingen, eind-LSN)."""
        with self.con.cursor() as cur:
            cur.execute("SELECT data FROM pg_logical_slot_peek_binary_changes(%s, NULL, %s, "
                        "'proto_version', '1', 'publication_names', %s)", (self.naam, aantal, self.pub))
            dec = Decoder(psycopg2_omzetter(cur))
            uit = []
            for (data,) in cur.fetchall():
                uit += dec.bericht(data)
        self.con.commit()
        return uit, dec.eind, dec.toast

    def schuif_op(self, eind):
        with self.con.cursor() as cur:
            cur.execute("SELECT pg_replication_slot_advance(%s, %s::pg_lsn)", (self.naam, lsn_tekst(eind)))
        self.con.commit()

    def weg(self):
        with self.con.cursor() as cur:
            cur.execute("SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots "
                        "WHERE slot_name = %s AND NOT active", (self.naam,))
        self.con.commit()


# --- Wegschrijven --------------------------------------------------------------------

def per_tabel(wijzigingen, schema, tabellen):
    """Per tabel van de bron de wijzigingen als rijen, met de kolommen van CDC erbij."""
    uit = {t: [] for t in tabellen}
    for bewerking, s, t, rij, commit, eind in wijzigingen:
        if s != schema or t not in uit:
            continue
        rij = dict(rij, _cdc_bewerking=bewerking, _cdc_lsn=lsn_tekst(eind), _cdc_tijdstip=commit)
        uit[t].append(rij)
    return uit


def laatste(rijen):
    """De laatste wijziging per id: wat in de stand komt, en welke id's eruit moeten."""
    per_id = {}
    for rij in rijen:
        per_id[rij["id"]] = rij
    bij = [r for r in per_id.values() if r["_cdc_bewerking"] != "D"]
    weg = [i for i, r in per_id.items() if r["_cdc_bewerking"] == "D"]
    return bij, weg


def resources(bron, laag, rijen_per_tabel, stand):
    uit, weg = [], {}
    for t, rijen in rijen_per_tabel.items():
        if not rijen:
            continue
        if stand:
            rijen, weg[t] = laatste(rijen)
            rijen = [{k: v for k, v in r.items() if k != "_cdc_bewerking"} for r in rijen]
            if not rijen:
                continue
        uit.append(dlt.resource(rijen, name=t, table_name=t, primary_key="id",
                                write_disposition=bronnen_lagen(bron)[laag]))
    return uit, weg


def bronnen_lagen(bron):
    from ingestie import bronnen  # pylint: disable=import-outside-toplevel
    return bronnen.lagen(bron)


def verwijder_uit_stand(pijp, weg):
    """Wat in de bron verwijderd is, gaat ook uit de stand (Iceberg row-level delete)."""
    from pyiceberg.expressions import In  # pylint: disable=import-outside-toplevel
    n = 0
    with pijp.destination_client() as client:
        for t, ids in weg.items():
            if not ids:
                continue
            try:
                tabel = client.load_open_table("iceberg", t)
            except Exception:  # pylint: disable=broad-except
                continue  # de tabel bestaat nog niet: niets te verwijderen
            for i in range(0, len(ids), 1000):
                tabel.delete(In("id", ids[i:i + 1000]))
            n += len(ids)
    return n


def laad(bron, laag, con, pijp, pseudonimiseer, tabellen, incrementeel):
    """Eén laag van één bron via het slot. Geeft het aantal rijen per tabel en een verslag."""
    s = Slot(con, slot(laag), publicatie(bron))
    if not s.bestaat():
        s.maak()
        rijen = incrementeel()
        # Na een verloren slot zijn verwijderingen in de tussentijd gemist: die blijven in de stand.
        return rijen, {"slot": "aangemaakt", "inhaalslag": sum(rijen.values()), "verloren": s.verloren}
    stand = laag.endswith("_stand")
    totaal = {t: 0 for t in tabellen}
    verslag = {"slot": "gelezen", "porties": 0, "verwijderd": 0, "toast": 0}
    while True:
        wijzigingen, eind, toast = s.kijk()
        if eind is None:
            break
        res, weg = resources(bron, laag, per_tabel(wijzigingen, bron, tabellen), stand)
        if res:
            info = pijp.run([pseudonimiseer(r) for r in res], table_format="iceberg")
            info.raise_on_failed_jobs()
            norm = pijp.last_trace.last_normalize_info
            for t, n in (norm.row_counts if norm else {}).items():
                if t in totaal:
                    totaal[t] += n
        if stand:
            verslag["verwijderd"] += verwijder_uit_stand(pijp, weg)
        s.schuif_op(eind)
        verslag["porties"] += 1
        verslag["toast"] += toast
    return totaal, verslag
