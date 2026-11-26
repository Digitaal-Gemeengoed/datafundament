"""De job verwijderen: een goedgekeurd verwijderverzoek uitvoeren (DF-ADR-015).

Het portaal start deze job met het id van het verzoek en de HMAC van het BSN
(nooit het BSN zelf). De job:

1. zoekt in de kluis het pseudoniem bij de HMAC;
2. zoekt in de BRP-lagen de persoonslijst(en) met dat pseudoniem (pl_id);
3. verwijdert alle rijen van die persoonslijsten uit ruw_brp, ruw_brp_stand en de
   uniforme laag, en de persoonsgebonden rijen (sociaal domein) met het pseudoniem;
4. ruimt in die tabellen alle oude snapshots op, zodat time travel de rijen niet
   terugbrengt;
5. zet de pl_id's op de blokkadelijst (een volgende ingestie slaat ze over) en
   vernietigt het pseudoniem in de kluis (crypto-shredding);
6. legt het bewijs vast als logregel "BEWIJS {...}", die het portaal overneemt.

Het pseudoniem komt nergens in de log: via het verzoek en de HMAC zou het anders
weer naar het BSN te herleiden zijn. Wat blijft: pseudoniemen in andere bronnen
(WOZ, meldingen, zaken, belastingen), die nergens meer naartoe leiden, en de oude
Parquet-bestanden tot compaction (DF-ADR-014).

De job is herhaalbaar: een tweede keer vindt hij niets meer en rondt hij af.
"""

import json
from datetime import datetime, timezone

from dagster import Config, OpExecutionContext, job, op

PERSOONSGEBONDEN = {"ruw_sociaal", "ruw_sociaal_stand"}


class Verzoek(Config):
    verzoek: str
    bsn_hmac: str


@op(tags={"kind": "privacy"})
def verwijder_persoon(context: OpExecutionContext, config: Verzoek):
    from beheer import lakehouse, onderhoud  # pylint: disable=import-outside-toplevel
    from ingestie.pseudoniem import Kluis  # pylint: disable=import-outside-toplevel

    h = bytes.fromhex(config.bsn_hmac)
    if len(h) != 32:
        raise ValueError("bsn_hmac is geen HMAC-SHA256")
    kluis = Kluis()
    with kluis.con.cursor() as cur:
        cur.execute("SELECT pseudoniem, vernietigd FROM kluis.koppeling WHERE bsn_hmac = %s", (h,))
        rij = cur.fetchone()
    pseudoniem = str(rij[0]) if rij and rij[0] else None
    bewijs = {"verzoek": config.verzoek, "tijdstip": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "pseudoniem_gevonden": pseudoniem is not None, "al_vernietigd": bool(rij and rij[1])}

    verwijderd, opgeruimd, pl_ids = {}, 0, []
    if pseudoniem:
        con = lakehouse.verbind()
        tabellen = lakehouse.tabellen(con, ["ruw_brp", "ruw_sociaal", "uniform"])
        for schema in ("ruw_brp_stand", "ruw_brp"):
            if (schema, "persoonslijst") in tabellen:
                pl_ids += [r[0] for r in con.execute(
                    f'SELECT DISTINCT id FROM lakehouse."{schema}".persoonslijst WHERE pseudoniem = ?', [pseudoniem]).fetchall()]
        pl_ids = sorted(set(pl_ids))
        lijst = ", ".join(str(int(i)) for i in pl_ids)
        for (schema, tabel), kolommen in sorted(tabellen.items()):
            waar = None
            if pl_ids and tabel == "persoonslijst" and schema.startswith("ruw_brp"):
                waar = f"id IN ({lijst})"
            elif pl_ids and "pl_id" in kolommen and (schema.startswith("ruw_brp") or schema == "uniform"):
                waar = f"pl_id IN ({lijst})"
            elif schema in PERSOONSGEBONDEN and "pseudoniem" in kolommen:
                waar = "pseudoniem = $p"
            if not waar:
                continue
            q = f'DELETE FROM lakehouse."{schema}"."{tabel}" WHERE {waar.replace("$p", "?")}'
            n = con.execute(q, [pseudoniem] if "$p" in waar else []).fetchone()
            n = n[0] if n else 0
            if n:
                verwijderd[f"{schema}.{tabel}"] = n
        con.close()
        # Oude snapshots weg in de tabellen waar iets is verwijderd: time travel brengt het niet terug.
        opgeruimd = onderhoud.alle_oude_snapshots_weg([k.split(".") for k in verwijderd], log=context.log.info)

    kluis.blokkeer("brp", pl_ids, config.verzoek)
    kluis.vernietig(h, config.verzoek)
    kluis.bevestig()
    bewijs.update({"persoonslijsten": len(pl_ids), "rijen_verwijderd": sum(verwijderd.values()),
                   "per_tabel": verwijderd, "snapshots_opgeruimd": opgeruimd, "pseudoniem_vernietigd": True,
                   "geblokkeerd_voor_ingestie": len(pl_ids),
                   "blijft": "pseudoniemen in WOZ, meldingen, zaken en belastingen (niet meer te herleiden); "
                             "oude Parquet-bestanden tot compaction"})
    context.log.info("BEWIJS " + json.dumps(bewijs, ensure_ascii=False))
    return bewijs


@job(description="Een goedgekeurd verwijderverzoek uitvoeren (DF-ADR-015). Wordt gestart vanuit het portaal.",
     tags={"dagster/max_retries": "0"})
def verwijderen():
    verwijder_persoon()


