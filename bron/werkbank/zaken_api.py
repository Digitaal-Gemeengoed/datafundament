"""Zaken-API van het zaaksysteem, naar het voorbeeld van de ZGW-API's (DF-ADR-014).

Een gemeente krijgt zaakgegevens zelden uit de database van de leverancier; ze
komen via een API. Deze API biedt de zaken uit het schema 'zaken' aan zoals de
Zaken-API en de Catalogi-API van VNG dat doen, alleen lezen:

  GET /catalogi/api/v1/zaaktypen
  GET /zaken/api/v1/zaken          ?registratiedatum__gt=JJJJ-MM-DD
  GET /zaken/api/v1/statussen
  GET /zaken/api/v1/rollen         de initiator: BSN of NNP (betrokkeneIdentificatie)
  GET /zaken/api/v1/zaakobjecten   het BAG-object van de zaak

Pagina's van 100, met count, next, previous en results, zoals de standaard.
Inloggen ook zoals ZGW: een JWT (HS256) met client_id, ondertekend met een
gedeeld geheim (ZAKEN_API_GEHEIM).

Eén uitbreiding op de standaard: ?gewijzigd__gt=<tijdstip> en het veld
gewijzigdOp. De ZGW-API's kennen geen filter op wijzigingen; in de praktijk
gebruik je daarvoor de Notificaties-API of haal je alles opnieuw op. Zonder
deze uitbreiding moet de ingestie elke keer alle zaken lezen.

    uvicorn zaken_api:app --host 0.0.0.0 --port 8000
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import date, datetime, timedelta

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request

PAGINA = 100
BRONORGANISATIE = "000000000"  # verzonnen RSIN
BAG = "https://bag.basisregistraties.overheid.nl/bag/id"
CLIENT_ID = os.environ.get("ZAKEN_API_CLIENT", "datafundament")

app = FastAPI(title="Zaken-API (synthetisch, ZGW-achtig)", version="1.0.0",
              description="Alleen lezen. Synthetische zaken voor het Datafundament.")


# --- Inloggen: JWT zoals de ZGW-API's ----------------------------------------------

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def maak_token(geheim, client_id=CLIENT_ID):
    kop = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    inhoud = _b64(json.dumps({"iss": client_id, "client_id": client_id, "iat": int(time.time())}).encode())
    handtekening = _b64(hmac.new(geheim.encode(), f"{kop}.{inhoud}".encode(), hashlib.sha256).digest())
    return f"{kop}.{inhoud}.{handtekening}"


def controleer_token(token, geheim):
    try:
        kop, inhoud, handtekening = token.split(".")
        verwacht = _b64(hmac.new(geheim.encode(), f"{kop}.{inhoud}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(verwacht, handtekening) or json.loads(_unb64(kop)).get("alg") != "HS256":
            return None
        return json.loads(_unb64(inhoud))
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def ingelogd(request: Request):
    geheim = os.environ.get("ZAKEN_API_GEHEIM")
    if not geheim:
        raise HTTPException(503, "ZAKEN_API_GEHEIM ontbreekt")
    auth = request.headers.get("authorization", "")
    claims = controleer_token(auth[7:], geheim) if auth.lower().startswith("bearer ") else None
    if not claims:
        raise HTTPException(401, "Ongeldige of ontbrekende JWT", headers={"WWW-Authenticate": "Bearer"})
    if claims.get("client_id") != CLIENT_ID:
        raise HTTPException(403, "Deze client heeft geen toegang")
    return claims


# --- Database en opmaak ----------------------------------------------------------------

def rijen(sql, args):
    with psycopg.connect(autocommit=True) as con, con.cursor() as cur:
        cur.execute(sql, args)
        namen = [d[0] for d in cur.description]
        return [dict(zip(namen, r)) for r in cur.fetchall()]


def basis(request):
    return os.environ.get("BASIS_URL") or str(request.base_url).rstrip("/")


def uid(soort, sleutel):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"datafundament:{soort}:{sleutel}"))


def tijd(t):
    return t.isoformat() if isinstance(t, datetime) else t


def pagina(request, sql, args, opmaak, page):
    if page < 1:
        raise HTTPException(400, "page begint bij 1")
    alles = rijen(f"SELECT count(*) AS n FROM ({sql}) x", args)[0]["n"]
    data = rijen(f"{sql} LIMIT %s OFFSET %s", args + [PAGINA, (page - 1) * PAGINA])

    def link(p):
        params = dict(request.query_params)
        params["page"] = str(p)
        return str(request.url.replace_query_params(**params))

    b = basis(request)
    return {"count": alles,
            "next": link(page + 1) if page * PAGINA < alles else None,
            "previous": link(page - 1) if page > 1 else None,
            "results": [opmaak(r, b) for r in data]}


def filters(gewijzigd__gt, kolom="gewijzigd_op"):
    if gewijzigd__gt is None:
        return "", []
    try:
        t = datetime.fromisoformat(gewijzigd__gt.replace("Z", "+00:00").replace(" ", "+"))
    except ValueError as e:
        raise HTTPException(400, "gewijzigd__gt: geen geldig tijdstip (ISO 8601)") from e
    return f" AND {kolom} > %s", [t]


ZAAK_SQL = """
    SELECT z.*, t.omschrijving AS zaaktype_omschrijving, t.doorlooptijd_dagen,
           (SELECT s.id FROM zaken.status s WHERE s.zaak_identificatie = z.identificatie
            ORDER BY s.datum_status_gezet DESC, s.id DESC LIMIT 1) AS status_id
    FROM zaken.zaak z JOIN zaken.zaaktype t ON t.identificatie = z.zaaktype_identificatie
    WHERE true"""


# --- Endpoints --------------------------------------------------------------------------

@app.get("/catalogi/api/v1/zaaktypen")
def zaaktypen(request: Request, page: int = 1, _=Depends(ingelogd)):
    def opmaak(r, b):
        return {"url": f"{b}/catalogi/api/v1/zaaktypen/{uid('zaaktype', r['identificatie'])}",
                "identificatie": r["identificatie"], "omschrijving": r["omschrijving"],
                "doorlooptijd": f"P{r['doorlooptijd_dagen']}D", "gewijzigdOp": tijd(r["gewijzigd_op"])}
    return pagina(request, "SELECT * FROM zaken.zaaktype ORDER BY identificatie", [], opmaak, page)


@app.get("/zaken/api/v1/zaken")
def zaken(request: Request, page: int = 1, registratiedatum__gt: date | None = None,
          gewijzigd__gt: str | None = None, _=Depends(ingelogd)):
    extra, args = filters(gewijzigd__gt, "z.gewijzigd_op")
    if registratiedatum__gt:
        extra += " AND z.registratiedatum > %s"
        args.append(registratiedatum__gt)

    def opmaak(r, b):
        u = uid("zaak", r["identificatie"])
        gepland = r["registratiedatum"] + timedelta(days=r["doorlooptijd_dagen"])
        return {"url": f"{b}/zaken/api/v1/zaken/{u}", "uuid": u, "identificatie": r["identificatie"],
                "bronorganisatie": BRONORGANISATIE, "omschrijving": r["zaaktype_omschrijving"],
                "zaaktype": f"{b}/catalogi/api/v1/zaaktypen/{uid('zaaktype', r['zaaktype_identificatie'])}",
                "registratiedatum": r["registratiedatum"].isoformat(), "startdatum": r["registratiedatum"].isoformat(),
                "einddatumGepland": gepland.isoformat(), "uiterlijkeEinddatumAfdoening": gepland.isoformat(),
                "einddatum": r["einddatum"].isoformat() if r["einddatum"] else None,
                "status": f"{b}/zaken/api/v1/statussen/{uid('status', r['status_id'])}" if r["status_id"] else None,
                "resultaattoelichting": r["resultaat"], "vertrouwelijkheidaanduiding": "zaakvertrouwelijk",
                "gewijzigdOp": tijd(r["gewijzigd_op"])}
    return pagina(request, ZAAK_SQL + extra + " ORDER BY z.gewijzigd_op, z.id", args, opmaak, page)


@app.get("/zaken/api/v1/statussen")
def statussen(request: Request, page: int = 1, gewijzigd__gt: str | None = None, _=Depends(ingelogd)):
    extra, args = filters(gewijzigd__gt)

    def opmaak(r, b):
        u = uid("status", r["id"])
        return {"url": f"{b}/zaken/api/v1/statussen/{u}", "uuid": u,
                "zaak": f"{b}/zaken/api/v1/zaken/{uid('zaak', r['zaak_identificatie'])}",
                "statustype": f"{b}/catalogi/api/v1/statustypen/{uid('statustype', r['statustype'])}",
                "datumStatusGezet": tijd(r["datum_status_gezet"]), "statustoelichting": r["statustype"],
                "gewijzigdOp": tijd(r["gewijzigd_op"])}
    return pagina(request, f"SELECT * FROM zaken.status WHERE true{extra} ORDER BY gewijzigd_op, id", args,
                  opmaak, page)


@app.get("/zaken/api/v1/rollen")
def rollen(request: Request, page: int = 1, gewijzigd__gt: str | None = None, _=Depends(ingelogd)):
    extra, args = filters(gewijzigd__gt)

    def opmaak(r, b):
        u = uid("rol", r["identificatie"])
        persoon = r["initiator_bsn"] is not None
        return {"url": f"{b}/zaken/api/v1/rollen/{u}", "uuid": u,
                "zaak": f"{b}/zaken/api/v1/zaken/{uid('zaak', r['identificatie'])}",
                "betrokkeneType": "natuurlijk_persoon" if persoon else "niet_natuurlijk_persoon",
                "omschrijvingGeneriek": "initiator", "roltoelichting": "Aanvrager",
                "betrokkeneIdentificatie": {"inpBsn": r["initiator_bsn"]} if persoon
                else {"innNnpId": r["initiator_nnp_id"]},
                "gewijzigdOp": tijd(r["gewijzigd_op"])}
    return pagina(request, "SELECT identificatie, initiator_bsn, initiator_nnp_id, gewijzigd_op, id FROM zaken.zaak "
                           "WHERE (initiator_bsn IS NOT NULL OR initiator_nnp_id IS NOT NULL)"
                           f"{extra} ORDER BY gewijzigd_op, id", args, opmaak, page)


@app.get("/zaken/api/v1/zaakobjecten")
def zaakobjecten(request: Request, page: int = 1, gewijzigd__gt: str | None = None, _=Depends(ingelogd)):
    extra, args = filters(gewijzigd__gt)

    def opmaak(r, b):
        u = uid("zaakobject", r["identificatie"])
        pand = r["object_identificatie"][4:6] == "10"
        soort = "pand" if pand else "verblijfsobject"
        return {"url": f"{b}/zaken/api/v1/zaakobjecten/{u}", "uuid": u,
                "zaak": f"{b}/zaken/api/v1/zaken/{uid('zaak', r['identificatie'])}",
                "object": f"{BAG}/{soort}/{r['object_identificatie']}",
                "objectType": "pand" if pand else "adres",
                "objectIdentificatie": {"identificatie": r["object_identificatie"]},
                "gewijzigdOp": tijd(r["gewijzigd_op"])}
    return pagina(request, "SELECT identificatie, object_identificatie, gewijzigd_op, id FROM zaken.zaak "
                           f"WHERE object_identificatie IS NOT NULL{extra} ORDER BY gewijzigd_op, id",
                  args, opmaak, page)


@app.get("/")
def wortel():
    return {"zaken": "/zaken/api/v1/", "catalogi": "/catalogi/api/v1/", "docs": "/docs"}
