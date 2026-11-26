"""Nachtelijke export van het belastingsysteem, zoals een leverancier die aanlevert (DF-ADR-014).

Het datafundament leest de belastingen niet uit de database, maar krijgt elke
nacht een bestand: de aanslagen die sinds de vorige export zijn gewijzigd. De
eerste keer alles. Het formaat is dat van een doorsnee leverancier: CSV met
puntkomma's, een komma als decimaalteken, datums als dd-mm-jjjj en kopjes in
gewone taal. Uniformeren gebeurt in het lakehouse.

Het bestand gaat naar de bucket 'landing' in Garage op dfc, met een sleutel
die alleen mag schrijven (LANDING_SLEUTEL, LANDING_GEHEIM). Voor tests kan
het ook naar een map (LANDING_MAP).
"""

import csv
import io
import os
from datetime import datetime, timezone

KOPPEN = ["Aanslagnummer", "Belastingjaar", "Soort belasting", "BSN", "NNP-id", "WOZ-objectnummer", "Bedrag",
          "Dagtekening", "Status", "Mutatiedatum"]


def _bedrag(x):
    return f"{x:.2f}".replace(".", ",")


def _datum(d):
    return d.strftime("%d-%m-%Y") if d else ""


def bestand(rijen):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(KOPPEN)
    for r in rijen:
        w.writerow([r[0], r[1], r[2], r[3] or "", r[4] or "", r[5] or "", _bedrag(r[6]), _datum(r[7]), r[8],
                    r[9].astimezone(timezone.utc).strftime("%d-%m-%Y %H:%M:%S")])
    return buf.getvalue().encode("utf-8-sig")  # met BOM, zoals Excel het graag heeft


def afleveren(naam, inhoud):
    map_ = os.environ.get("LANDING_MAP")
    if map_:
        pad = os.path.join(map_, naam)
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        with open(pad, "wb") as f:
            f.write(inhoud)
        return pad
    import boto3  # pylint: disable=import-outside-toplevel
    from botocore.config import Config  # pylint: disable=import-outside-toplevel
    for n in ("LANDING_SLEUTEL", "LANDING_GEHEIM"):
        if not os.environ.get(n):
            raise SystemExit(f"{n} ontbreekt. Op dfw: sudo ./bron.sh landing-sleutel (de sleutel komt van dfc)")
    s3 = boto3.client("s3", endpoint_url=os.environ.get("LANDING_ENDPOINT", "http://10.67.0.1:3900"),
                      aws_access_key_id=os.environ["LANDING_SLEUTEL"],
                      aws_secret_access_key=os.environ["LANDING_GEHEIM"], region_name="garage",
                      config=Config(s3={"addressing_style": "path"}))
    s3.put_object(Bucket="landing", Key=naam, Body=inhoud, ContentType="text/csv; charset=utf-8")
    return f"s3://landing/{naam}"


def belastingen(con):
    with con.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS sim; CREATE TABLE IF NOT EXISTS sim.export "
                    "(bron text PRIMARY KEY, tot timestamptz NOT NULL)")
        cur.execute("SELECT tot FROM sim.export WHERE bron = 'belastingen'")
        rij = cur.fetchone()
        vanaf = rij[0] if rij else None
        # Alles wat sinds de vorige export gewijzigd is. De volgende export begint tien
        # minuten vóór nu: een transactie die nu nog loopt, heeft een gewijzigd_op van vóór
        # haar commit en valt zo niet tussen twee exports. Een regel kan dus twee keer
        # komen (minstens één keer, zoals bij de meeste koppelingen).
        cur.execute("SELECT now(), now() - interval '10 minutes'")
        nu, tot = cur.fetchone()
        cur.execute("SELECT aanslagnummer, belastingjaar, soort, subject_bsn, subject_nnp_id, wozobjectnummer, bedrag, "
                    "dagtekening, status, gewijzigd_op FROM belastingen.aanslag "
                    "WHERE %s::timestamptz IS NULL OR gewijzigd_op > %s ORDER BY aanslagnummer", (vanaf, vanaf))
        rijen = cur.fetchall()
        soort = "volledig" if vanaf is None else "mutaties"
        naam = f"belastingen/aanslag/aanslagen_{soort}_{nu.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}.csv"
        waar = afleveren(naam, bestand(rijen))
        cur.execute("INSERT INTO sim.export (bron, tot) VALUES ('belastingen', %s) "
                    "ON CONFLICT (bron) DO UPDATE SET tot = EXCLUDED.tot", (tot,))
    con.commit()
    print(f"Export belastingen ({soort}): {len(rijen)} aanslagen naar {waar}")
    return waar


if __name__ == "__main__":  # handig bij testen
    print(bestand([("202700000001", 2027, "OZB eigenaren", "999100015", None, "051800000001", 123.4,
                    datetime(2027, 2, 26).date(), "openstaand", datetime.now(timezone.utc))]).decode("utf-8-sig"))
