"""Lakekeeper inrichten: bootstrap, gebruikers, het warehouse 'datafundament' en de rechten.

Lakekeeper logt in via Keycloak en houdt de rechten bij in OpenFGA (DF-ADR-019).
Elk onderdeel heeft een eigen service-account in Keycloak (server/keycloak.sh):

  df-lk-beheer  dit script: wordt bij de bootstrap beheerder van de server
  df-lk-werk    dlt, dbt, onderhoud: namespaces en tabellen maken en wijzigen
  df-lk-trino   Trino: alleen lezen

De eerste beheerder in Keycloak (LK_BEHEERDER_SUB) wordt ook beheerder in
Lakekeeper, voor de web-UI. Opnieuw draaien kan: wat er al is, blijft.

Het warehouse staat op Garage, zonder STS en zonder remote signing (Garage kent
geen STS, DF-ADR-002); elke engine heeft een eigen sleutel voor Garage.

    python -m beheer.inrichten

Eindigt met code 3 als Lakekeeper al is ingericht zonder dat df-lk-beheer
beheerder is (de overstap van allowall naar OpenFGA). Het installatiescript
draait dan `lakekeeper reopen-bootstrap --yes` en start dit opnieuw.
"""

import os
import sys
import time

import requests

LAKEKEEPER = os.environ.get("LAKEKEEPER_URL", "http://lakekeeper:8181")
TOKEN_URL = os.environ.get("LK_TOKEN_URL") or (
    f"https://id.{os.environ.get('DOMEIN', '')}/realms/datafundament/protocol/openid-connect/token")
WAREHOUSE = "datafundament"
# Wat elk service-account mag op het warehouse (en alles daaronder).
RECHTEN = {"df-lk-werk": ["create", "modify"], "df-lk-trino": ["select"]}


def token(client_id, geheim):
    r = requests.post(TOKEN_URL, data={"grant_type": "client_credentials", "client_id": client_id,
                                       "client_secret": geheim, "scope": "lakekeeper"}, timeout=15)
    if not r.ok:
        sys.exit(f"Geen token van Keycloak voor {client_id}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


class Lakekeeper:
    def __init__(self, tok):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {tok}"

    def __call__(self, methode, pad, **kw):
        return self.s.request(methode, f"{LAKEKEEPER}/management/v1{pad}", timeout=30, **kw)


def wacht():
    for _ in range(60):
        try:
            if requests.get(f"{LAKEKEEPER}/health", timeout=2).status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    sys.exit("Lakekeeper antwoordt niet na 2 minuten.")


def bootstrap(lk):
    r = lk("POST", "/bootstrap", json={"accept-terms-of-use": True, "user-type": "application",
                                       "user-name": "df-lk-beheer (inrichten)"})
    if r.ok:
        print("  ✓ Lakekeeper ingericht (bootstrap); df-lk-beheer is beheerder")
        return
    if "already" not in r.text.lower() and r.status_code not in (400, 409):
        sys.exit(f"Bootstrap mislukt: {r.status_code} {r.text[:300]}")
    # Al ingericht: is df-lk-beheer ook beheerder? Zo niet: de overstap naar OpenFGA.
    if lk("GET", "/permissions/server/assignments").status_code in (401, 403):
        print("  ! Lakekeeper is al ingericht, maar df-lk-beheer is geen beheerder (overstap naar OpenFGA)")
        sys.exit(3)
    print("  ✓ Lakekeeper was al ingericht")


def gebruiker(client_id, geheim):
    """Het service-account meldt zich zelf aan; geeft zijn id in Lakekeeper."""
    r = Lakekeeper(token(client_id, geheim))("POST", "/user", json={"update-if-exists": True})
    if not r.ok:
        sys.exit(f"Gebruiker {client_id} aanmelden mislukt: {r.status_code} {r.text[:300]}")
    return r.json()["id"]


def beheerder(lk):
    """De eerste beheerder uit Keycloak: beheerder van de server en het project."""
    sub = os.environ.get("LK_BEHEERDER_SUB")
    if not sub:
        print("  ! Geen LK_BEHEERDER_SUB: nog geen mens als beheerder in Lakekeeper")
        return
    uid = f"oidc~{sub}"
    email = os.environ.get("LK_BEHEERDER_EMAIL") or None
    r = lk("POST", "/user", json={"id": uid, "name": email or uid, "email": email, "user-type": "human",
                                  "update-if-exists": True})
    if not r.ok:
        sys.exit(f"Beheerder aanmaken mislukt: {r.status_code} {r.text[:300]}")
    toewijzen(lk, "/permissions/server/assignments", [("admin", uid)])
    toewijzen(lk, "/permissions/project/assignments", [("project_admin", uid)])
    print(f"  ✓ {email or uid} is beheerder in Lakekeeper (web-UI)")


def toewijzen(lk, pad, gewenst):
    """Alleen wat ontbreekt; een bestaande toewijzing nog eens schrijven geeft een fout."""
    r = lk("GET", pad)
    r.raise_for_status()
    er = {(a.get("type"), a.get("user")) for a in r.json().get("assignments", [])}
    nieuw = [{"type": t, "user": u} for t, u in gewenst if (t, u) not in er]
    if nieuw:
        r = lk("POST", pad, json={"writes": nieuw})
        if not r.ok:
            sys.exit(f"Rechten zetten mislukt ({pad}): {r.status_code} {r.text[:300]}")
    return len(nieuw)


def warehouse(lk):
    r = lk("GET", "/warehouse")
    r.raise_for_status()
    for w in r.json().get("warehouses", []):
        if w.get("name") == WAREHOUSE:
            print(f"  ✓ Warehouse '{WAREHOUSE}' bestond al")
            return w["id"]
    body = {
        "warehouse-name": WAREHOUSE,
        "storage-profile": {
            "type": "s3",
            "bucket": os.environ.get("LK_BUCKET", "lakehouse"),
            "key-prefix": "warehouse",
            "region": "garage",
            "endpoint": os.environ.get("LK_S3_ENDPOINT", "http://garage:3900"),
            "path-style-access": True,
            "flavor": "s3-compat",
            "sts-enabled": False,
            "remote-signing-enabled": False,
        },
        "storage-credential": {
            "type": "s3",
            "credential-type": "access-key",
            "aws-access-key-id": os.environ["GARAGE_LAKEKEEPER_SLEUTEL"],
            "aws-secret-access-key": os.environ["GARAGE_LAKEKEEPER_GEHEIM"],
        },
    }
    r = lk("POST", "/warehouse", json=body)
    if not r.ok:
        sys.exit(f"Warehouse maken mislukt: {r.status_code} {r.text[:300]}")
    print(f"  ✓ Warehouse '{WAREHOUSE}' aangemaakt; Lakekeeper heeft schrijven en lezen op Garage gecontroleerd")
    return r.json()["warehouse-id"] if "warehouse-id" in r.json() else r.json()["id"]


def main():
    wacht()
    lk = Lakekeeper(token("df-lk-beheer", os.environ["LK_BEHEER_GEHEIM"]))
    bootstrap(lk)
    # Ook projectbeheerder: na de overstap van allowall bestaat het project al, en dan geeft
    # beheerder van de server nog geen recht om er een warehouse in te maken of te zien.
    ik = lk("GET", "/whoami").json()["id"]
    toewijzen(lk, "/permissions/project/assignments", [("project_admin", ik)])
    ids = {"df-lk-werk": gebruiker("df-lk-werk", os.environ["LK_WERK_GEHEIM"]),
           "df-lk-trino": gebruiker("df-lk-trino", os.environ["LK_TRINO_GEHEIM"])}
    beheerder(lk)
    wid = warehouse(lk)
    n = toewijzen(lk, f"/permissions/warehouse/{wid}/assignments",
                  [(recht, ids[c]) for c, rechten in RECHTEN.items() for recht in rechten])
    print(f"  ✓ Rechten op het warehouse: df-lk-werk maken en wijzigen, df-lk-trino lezen"
          f"{f' ({n} nieuw)' if n else ''}")


if __name__ == "__main__":
    main()
