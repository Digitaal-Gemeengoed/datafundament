#!/usr/bin/env bash
# De bron op dfw bedienen.
#
#   sudo ./bron.sh start              database starten (eerste keer: wachtwoorden maken)
#   sudo ./bron.sh laden              testpersonen (opnieuw) laden
#   sudo ./bron.sh verhuis [BSN]      een persoon verhuist (demo CDC)
#   sudo ./bron.sh overlijden [BSN]   een persoon overlijdt (demo CDC)
#   sudo ./bron.sh kolom-erbij        nieuwe kolom in de bron (demo schemawijziging)
#   sudo ./bron.sh status             aantallen, laatste wijzigingen, replicatie
#   sudo ./bron.sh psql               SQL-prompt in de bron
#   sudo ./bron.sh dlt-wachtwoord     het wachtwoord van dlt_lezer, voor dfc
#   sudo ./bron.sh opnieuw            alles weg en opnieuw beginnen (vraagt eerst)
set -euo pipefail
cd "$(dirname "$0")"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
stop() { printf '\n\033[1;31mGestopt:\033[0m %s\n\n' "$*" >&2; exit 1; }

maak_env() {
  [ -f .env ] && return 0
  umask 077
  cat > .env <<EOF
BRON_WACHTWOORD=$(openssl rand -hex 24)
DLT_WACHTWOORD=$(openssl rand -hex 24)
WG_ADRES=10.67.0.2
EOF
  umask 022
  ok "Wachtwoorden gemaakt in $(pwd)/.env"
}

start() {
  maak_env
  grep -q '^WG_ADRES=10\.67\.0\.2$' .env && ! ip -4 addr show wg0 2>/dev/null | grep -q '10\.67\.0\.2/' \
    && stop "WireGuard (10.67.0.2) draait niet. Koppel eerst: sudo /opt/datafundament/server/koppelen.sh"
  docker compose up -d --wait db
  docker compose --profile werk build -q werkbank
  ok "De bron draait op $(grep '^WG_ADRES=' .env | cut -d= -f2):5432"
}

werkbank() { docker compose --profile werk run --rm -T werkbank "$@"; }

case "${1:-help}" in
  start) start ;;
  laden|verhuis|overlijden|kolom-erbij|status) maak_env; werkbank "$@" ;;
  psql) docker compose exec db psql -U bron bron ;;
  dlt-wachtwoord) grep '^DLT_WACHTWOORD=' .env | cut -d= -f2 ;;
  opnieuw)
    read -r -p "Alles in de bron wordt gewist, ook het replicatieslot. Doorgaan? [ja/nee] " a
    [[ "${a,,}" =~ ^(j|ja)$ ]] || exit 0
    docker compose --profile werk down -v
    start
    werkbank laden ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
