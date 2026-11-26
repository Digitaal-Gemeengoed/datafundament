"""De Zaken-API op dfw als bron voor dlt (DF-ADR-014).

dlt leest de API zoals elke REST-API: pagina voor pagina (de next-link), met
een JWT zoals de ZGW-API's die vragen, en incrementeel op gewijzigdOp. Dat
filter is een uitbreiding op de standaard; zie bron/werkbank/zaken_api.py.

Configuratie: ZAKEN_API_URL (standaard http://10.67.0.2:8000) en ZAKEN_API_GEHEIM.
"""

import base64
import hashlib
import hmac
import json
import os
import time

from dlt.sources.rest_api import rest_api_source

BEGIN = "1970-01-01T00:00:00+00:00"


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def token(geheim, client_id="datafundament"):
    """JWT (HS256) met client_id, zoals de ZGW-API's die verwachten."""
    kop = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    inhoud = _b64(json.dumps({"iss": client_id, "client_id": client_id, "iat": int(time.time())}).encode())
    return f"{kop}.{inhoud}." + _b64(hmac.new(geheim.encode(), f"{kop}.{inhoud}".encode(), hashlib.sha256).digest())


def source(schrijfwijze):
    def bron(naam, pad):
        return {
            "name": naam,
            "write_disposition": schrijfwijze,
            "endpoint": {
                "path": pad,
                "params": {"gewijzigd__gt": {"type": "incremental", "cursor_path": "gewijzigdOp",
                                             "initial_value": BEGIN}},
            },
        }

    return rest_api_source({
        "client": {
            "base_url": os.environ.get("ZAKEN_API_URL", "http://10.67.0.2:8000"),
            "auth": {"type": "bearer", "token": token(os.environ["ZAKEN_API_GEHEIM"])},
            "paginator": {"type": "json_link", "next_url_path": "next"},
        },
        "resource_defaults": {"primary_key": "uuid", "endpoint": {"data_selector": "results"}},
        "resources": [
            {"name": "zaaktypen", "primary_key": "url", "write_disposition": "replace",
             "endpoint": {"path": "catalogi/api/v1/zaaktypen"}},
            bron("zaken", "zaken/api/v1/zaken"),
            bron("statussen", "zaken/api/v1/statussen"),
            bron("rollen", "zaken/api/v1/rollen"),
            bron("zaakobjecten", "zaken/api/v1/zaakobjecten"),
        ],
    }, name="zaken")
