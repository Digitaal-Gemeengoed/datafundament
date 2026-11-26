#!/usr/bin/env bash
# De bron op dfw bedienen.
#
#   sudo ./bron.sh start              database en Zaken-API starten of bijwerken (na git pull)
#   sudo ./bron.sh laden              testpersonen (opnieuw) laden
#   sudo ./bron.sh synthetisch        synthetische inwoners en bronnen (bag, woz, mor, ...); zet de klok op start
#   sudo ./bron.sh verhuis [BSN]      een persoon verhuist (demo CDC)
#   sudo ./bron.sh overlijden [BSN]   een persoon overlijdt (demo CDC)
#   sudo ./bron.sh kolom-erbij        nieuwe kolom in de bron (demo schemawijziging)
#   sudo ./bron.sh melding            nieuwe melding openbare ruimte (demo CDC)
#   sudo ./bron.sh zaak-afhandelen    een open zaak afhandelen (demo API)
#   sudo ./bron.sh simuleer           de simulatieklok bijwerken tot nu
#   sudo ./bron.sh simulatie-aan      de klok elk uur laten lopen, export elke nacht (systemd)
#   sudo ./bron.sh simulatie-uit      de timers stoppen
#   sudo ./bron.sh simulatie-status   tot waar de klok is, en wat er laatst gebeurde
#   sudo ./bron.sh export-belastingen de export van de belastingen nu maken
#   sudo ./bron.sh landing-sleutel    de sleutel voor de landingsbucket invoeren (komt van dfc)
#   sudo ./bron.sh zaken-api-geheim   het geheim van de Zaken-API, voor dfc
#   sudo ./bron.sh dlt-wachtwoord     het wachtwoord van dlt_lezer, voor dfc
#   sudo ./bron.sh status             aantallen, laatste wijzigingen, replicatie
#   sudo ./bron.sh psql               SQL-prompt in de bron
#   sudo ./bron.sh opnieuw            alles weg en opnieuw beginnen (vraagt eerst)
set -euo pipefail
cd "$(dirname "$0")"
HIER="$(pwd)"
REPO="$(cd .. && pwd)"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
stop() { printf '\n\033[1;31mGestopt:\033[0m %s\n\n' "$*" >&2; exit 1; }

vul_aan() {  # NAAM WAARDE: alleen als NAAM nog niet in .env staat
  grep -q "^$1=" .env 2>/dev/null && return 0
  printf '%s=%s\n' "$1" "$2" >> .env
}

maak_env() {
  umask 077; touch .env; umask 022; chmod 600 .env
  vul_aan BRON_WACHTWOORD "$(openssl rand -hex 24)"
  vul_aan DLT_WACHTWOORD "$(openssl rand -hex 24)"
  vul_aan ZAKEN_API_DB_WACHTWOORD "$(openssl rand -hex 24)"
  vul_aan ZAKEN_API_GEHEIM "$(openssl rand -hex 32)"
  vul_aan WG_ADRES 10.67.0.2
}

waarde() { grep -m1 "^$1=" .env | cut -d= -f2-; }

start() {
  maak_env
  grep -q '^WG_ADRES=10\.67\.0\.2$' .env && ! ip -4 addr show wg0 2>/dev/null | grep -q '10\.67\.0\.2/' \
    && stop "WireGuard (10.67.0.2) draait niet. Koppel eerst: sudo /opt/datafundament/server/koppelen.sh"
  # Het poortfilter bijwerken (nieuwe poorten, zoals de Zaken-API).
  if [ -x /usr/local/sbin/df-docker-filter ] && ! cmp -s "$REPO/server/docker-filter.sh" /usr/local/sbin/df-docker-filter; then
    install -m 755 "$REPO/server/docker-filter.sh" /usr/local/sbin/df-docker-filter
    systemctl restart df-docker-filter
    ok "Poortfilter bijgewerkt"
  fi
  docker compose --profile werk build -q werkbank
  docker compose up -d --wait db
  # pg_hba.conf is een gekoppeld bestand: na een git pull ziet de container het nieuwe pas na een herstart.
  if ! docker compose exec -T db cat /etc/postgresql/pg_hba.conf | cmp -s - postgres/pg_hba.conf; then
    docker compose restart db >/dev/null && docker compose up -d --wait db
    ok "Database herstart (nieuwe toegangsregels)"
  fi
  # De rol van de Zaken-API bestaat pas na 'synthetisch'; daarna kan de API starten.
  if docker compose exec -T db psql -U bron -d bron -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'zaken_api'" | grep -q 1; then
    docker compose up -d zaken-api
    ok "De Zaken-API draait op $(waarde WG_ADRES):8000"
  else
    ok "De Zaken-API start na: sudo ./bron.sh synthetisch"
  fi
  ok "De bron draait op $(waarde WG_ADRES):5432"
}

werkbank() {
  if [ -n "${DF_GEEN_BUILD:-}" ]; then
    docker compose --profile werk run --rm -T werkbank "$@"
  else
    docker compose --profile werk run --build --rm -T werkbank "$@"
  fi
}

timers() {
  cat > /etc/systemd/system/df-simulatie.service <<EOF
[Unit]
Description=Datafundament: simulatieklok van de bron bijwerken
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
Environment=DF_GEEN_BUILD=1
ExecStart=$HIER/bron.sh simuleer
EOF
  cat > /etc/systemd/system/df-simulatie.timer <<'EOF'
[Unit]
Description=Datafundament: simulatieklok elk uur

[Timer]
OnCalendar=*-*-* *:03:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
  cat > /etc/systemd/system/df-export-belastingen.service <<EOF
[Unit]
Description=Datafundament: nachtelijke export van de belastingen naar de landingsbucket
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
Environment=DF_GEEN_BUILD=1
ExecStart=$HIER/bron.sh export-belastingen
EOF
  cat > /etc/systemd/system/df-export-belastingen.timer <<'EOF'
[Unit]
Description=Datafundament: export van de belastingen elke nacht

[Timer]
OnCalendar=*-*-* 02:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
}

case "${1:-help}" in
  start) start ;;
  laden|verhuis|overlijden|kolom-erbij|status|synthetisch|melding|zaak-afhandelen|simuleer|simulatie-status|export-belastingen)
    maak_env; werkbank "$@"
    if [ "$1" = synthetisch ]; then docker compose up -d zaken-api >/dev/null && ok "De Zaken-API draait"; fi ;;
  simulatie-aan)
    [ -n "$(waarde LANDING_SLEUTEL)" ] || echo "  Let op: nog geen landingssleutel; de export werkt pas na: sudo ./bron.sh landing-sleutel"
    docker compose --profile werk build -q werkbank
    timers
    systemctl enable --now df-simulatie.timer df-export-belastingen.timer >/dev/null
    ok "De klok loopt elk uur (3 over), de export draait elke nacht om 02:15"
    systemctl list-timers 'df-*' --no-pager ;;
  simulatie-uit)
    systemctl disable --now df-simulatie.timer df-export-belastingen.timer 2>/dev/null || true
    ok "Timers gestopt; de klok blijft staan waar hij is" ;;
  landing-sleutel)
    maak_env
    read -r -p "  Sleutel-id (GK...): " ID
    read -r -s -p "  Geheim: " GEHEIM; echo
    [[ "$ID" =~ ^GK[0-9a-f]{24}$ && "$GEHEIM" =~ ^[0-9a-f]{64}$ ]] || stop "Dat lijkt niet op een sleutel van Garage."
    sed -i '/^LANDING_SLEUTEL=/d; /^LANDING_GEHEIM=/d' .env
    printf 'LANDING_SLEUTEL=%s\nLANDING_GEHEIM=%s\n' "$ID" "$GEHEIM" >> .env
    ok "Opgeslagen in $HIER/.env" ;;
  zaken-api-geheim) maak_env; waarde ZAKEN_API_GEHEIM ;;
  dlt-wachtwoord) waarde DLT_WACHTWOORD ;;
  psql) docker compose exec db psql -U bron bron ;;
  opnieuw)
    read -r -p "Alles in de bron wordt gewist, ook het replicatieslot. Doorgaan? [ja/nee] " a
    [[ "${a,,}" =~ ^(j|ja)$ ]] || exit 0
    docker compose --profile werk down -v
    start
    werkbank laden
    werkbank synthetisch
    docker compose up -d zaken-api ;;
  *) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
