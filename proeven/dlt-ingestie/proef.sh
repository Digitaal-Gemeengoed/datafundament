#!/usr/bin/env bash
# Proef op dfc: dlt leest de bron op dfw en schrijft naar Iceberg.
#
#   cd /opt/datafundament/proeven/dlt-ingestie
#   sudo ./proef.sh
#
# Vooraf: de opstelling van ../iceberg-schrijfpad draait (sudo ../iceberg-schrijfpad/proef.sh),
# en de bron op dfw is geladen. Het script vraagt één keer het wachtwoord van
# dlt_lezer (op dfw: sudo ./bron.sh dlt-wachtwoord).
set -euo pipefail
cd "$(dirname "$0")"

docker compose -p df-proef-schrijfpad ps --status running lakekeeper 2>/dev/null | grep -q lakekeeper \
  || { echo "De opstelling van iceberg-schrijfpad draait niet. Start eerst: sudo ../iceberg-schrijfpad/proef.sh"; exit 1; }
ping -c 1 -W 2 10.67.0.2 >/dev/null || { echo "dfw (10.67.0.2) is niet bereikbaar via WireGuard."; exit 1; }

if [ ! -f .env ]; then
  read -r -s -p "Wachtwoord van dlt_lezer (op dfw: sudo ./bron.sh dlt-wachtwoord): " W; echo
  [[ "$W" =~ ^[0-9a-f]+$ ]] || { echo "Dat lijkt niet op het wachtwoord (alleen 0-9 en a-f)."; exit 1; }
  umask 077
  { echo "DLT_WACHTWOORD=$W"; grep -E '^GARAGE_(SLEUTEL|GEHEIM)=' ../iceberg-schrijfpad/.env; } > .env
  umask 022
fi

echo "== Image bouwen (eerste keer: een minuut)"
docker compose build -q
docker compose run --rm ingestie || true

echo
echo "== Trino leest wat dlt schreef"
trino() { docker compose -p df-proef-schrijfpad exec -T trino trino --output-format=ALIGNED --execute "$1" 2>&1 | sed 's/^/      /'; }
trino "SHOW TABLES FROM lakehouse.ruw_brp"
trino "SELECT 'ruw_brp' AS laag, count(*) AS rijen FROM lakehouse.ruw_brp.verblijfplaats UNION ALL SELECT 'ruw_brp_stand', count(*) FROM lakehouse.ruw_brp_stand.verblijfplaats"
echo
echo "Stuur de hele uitvoer door. Opruimen: sudo docker compose down; rm .env"
