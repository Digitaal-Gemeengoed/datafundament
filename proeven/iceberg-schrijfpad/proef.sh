#!/usr/bin/env bash
# Proef DF-ADR-004 op dfc: DuckDB → Lakekeeper → Garage, daarna lezen met Trino.
#
#   cd /opt/datafundament/proeven/iceberg-schrijfpad
#   sudo ./proef.sh              # opzetten en testen (eerste keer: een paar minuten)
#   sudo ./proef.sh opruimen     # alles weg, ook de data
#
# Niets wordt gepubliceerd; de proef raakt de rest van de server niet.
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = opruimen ]; then
  docker compose down -v --remove-orphans
  rm -f .env
  echo "Opgeruimd."
  exit 0
fi

# Geheimen voor de proef, één keer, alleen op deze server.
if [ ! -f .env ]; then
  umask 077
  cat > .env <<EOF
GARAGE_RPC_GEHEIM=$(openssl rand -hex 32)
GARAGE_SLEUTEL=GK$(openssl rand -hex 12)
GARAGE_GEHEIM=$(openssl rand -hex 32)
LK_DB_WACHTWOORD=$(openssl rand -hex 16)
LK_SLEUTEL=$(openssl rand -hex 32)
EOF
  umask 022
fi

echo "== Opstarten (images ophalen kan even duren)"
docker compose pull -q
docker compose up -d

echo "== Wachten tot DuckDB in de proefcontainer staat"
for _ in $(seq 1 90); do
  docker compose exec -T proef test -f /tmp/klaar 2>/dev/null && break
  sleep 2
done

DUCKDB=0
docker compose exec -T proef python /proef.py || DUCKDB=1

echo
echo "== Trino $(docker compose exec -T trino trino --version 2>/dev/null | tr -d '\r' || echo '?')"
for _ in $(seq 1 60); do
  docker compose exec -T trino trino --execute "SELECT 1" >/dev/null 2>&1 && break
  sleep 3
done
TRINO=0
trino_stap() {
  local naam="$1" sql="$2" uit
  if uit="$(docker compose exec -T trino trino --output-format=ALIGNED --execute "$sql" 2>&1)"; then
    echo "  ✓ $naam"; sed 's/^/      /' <<<"$uit"
  else
    echo "  ✗ $naam"; sed 's/^/      /' <<<"$uit" | tail -5; TRINO=1
  fi
}
trino_stap "Schema's in de catalogus zien" "SHOW SCHEMAS FROM lakehouse"
trino_stap "Tabel lezen, met de wijzigingen van DuckDB en geometrie uit WKB" \
  "SELECT id, naam, buurt, geboortejaar, ST_AsText(ST_GeomFromBinary(locatie)) AS locatie FROM lakehouse.proef.personen ORDER BY id"
trino_stap "Snapshots zien" \
  "SELECT committed_at, snapshot_id, operation FROM lakehouse.proef.\"personen\$snapshots\" ORDER BY committed_at"

echo
echo "== Versies (voor het vastpinnen in compose/)"
for d in garage lakekeeper trino; do
  c="$(docker compose ps -aq "$d" | head -1)"
  [ -n "$c" ] || { printf '  %-11s (draait niet)\n' "$d"; continue; }
  img="$(docker inspect --format '{{.Config.Image}}' "$c")"
  digest="$(docker image inspect --format '{{index .RepoDigests 0}}' "$img" 2>/dev/null || echo '?')"
  printf '  %-11s %s\n  %-11s %s\n' "$d" "$img" "" "$digest"
done
echo
if [ "$DUCKDB" = 0 ] && [ "$TRINO" = 0 ]; then
  echo "UITKOMST: het schrijfpad werkt. DuckDB schrijft, Trino leest. (DF-ADR-004, punt 1)"
else
  echo "UITKOMST: niet alles werkt; zie de ✗ hierboven. Stuur de hele uitvoer door."
fi
echo "Opruimen als je klaar bent: sudo ./proef.sh opruimen"
