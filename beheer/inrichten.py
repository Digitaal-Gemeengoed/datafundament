"""Lakekeeper inrichten: bootstrap en het warehouse 'datafundament' op Garage.

Zonder STS en zonder remote signing (Garage kent geen STS, DF-ADR-002); elke
engine heeft een eigen sleutel. Opnieuw draaien kan: wat er al is, blijft.

    python -m beheer.inrichten
"""

import os
import sys
import time

import requests

LAKEKEEPER = os.environ.get("LAKEKEEPER_URL", "http://lakekeeper:8181")
WAREHOUSE = "datafundament"


def wacht():
    for _ in range(60):
        try:
            if requests.get(f"{LAKEKEEPER}/health", timeout=2).status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    sys.exit("Lakekeeper antwoordt niet na 2 minuten.")


def bootstrap():
    r = requests.post(f"{LAKEKEEPER}/management/v1/bootstrap", json={"accept-terms-of-use": True}, timeout=10)
    if r.ok:
        print("  ✓ Lakekeeper ingericht (bootstrap)")
    elif "already" in r.text.lower():
        print("  ✓ Lakekeeper was al ingericht")
    else:
        sys.exit(f"Bootstrap mislukt: {r.status_code} {r.text}")


def warehouse():
    r = requests.get(f"{LAKEKEEPER}/management/v1/warehouse", timeout=10)
    r.raise_for_status()
    if any(w.get("name") == WAREHOUSE for w in r.json().get("warehouses", [])):
        print(f"  ✓ Warehouse '{WAREHOUSE}' bestond al")
        return
    body = {
        "warehouse-name": WAREHOUSE,
        "storage-profile": {
            "type": "s3",
            "bucket": "lakehouse",
            "key-prefix": "warehouse",
            "region": "garage",
            "endpoint": "http://garage:3900",
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
    r = requests.post(f"{LAKEKEEPER}/management/v1/warehouse", json=body, timeout=30)
    if not r.ok:
        sys.exit(f"Warehouse maken mislukt: {r.status_code} {r.text}")
    print(f"  ✓ Warehouse '{WAREHOUSE}' aangemaakt; Lakekeeper heeft schrijven en lezen op Garage gecontroleerd")


if __name__ == "__main__":
    wacht()
    bootstrap()
    warehouse()
