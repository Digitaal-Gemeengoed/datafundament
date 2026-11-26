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
#   sudo ./bron.sh kluis-inrichten    OpenBao de eerste keer inrichten (toont ontzegelsleutel en tokens)
#   sudo ./bron.sh kluis-ontzegel     OpenBao ontzegelen, na elke herstart
#   sudo ./bron.sh kluis-status       is de kluis ingericht en ontzegeld?
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
  docker compose up -d kluis >/dev/null
  case "$(kluis_stand)" in
    ok) ok "De kluis (OpenBao) is ontzegeld" ;;
    verzegeld) printf '  \033[33m!\033[0m De kluis is verzegeld. Ontzegel: sudo ./bron.sh kluis-ontzegel\n' ;;
    *) printf '  \033[33m!\033[0m De kluis is nog niet ingericht: sudo ./bron.sh kluis-inrichten\n' ;;
  esac
  ok "De bron draait op $(waarde WG_ADRES):5432"
}

bao() { docker compose exec -T kluis bao "$@"; }

kluis_stand() {  # ok | verzegeld | nieuw
  local s
  # bao status geeft 2 als de kluis verzegeld is; de JSON telt.
  for _ in $(seq 1 20); do
    s="$(bao status -format=json 2>/dev/null | tr -d ' \n' || true)"
    [ -n "$s" ] && break
    sleep 1
  done
  case "$s" in
    *'"initialized":false'*) echo nieuw ;;
    *'"sealed":true'*) echo verzegeld ;;
    *'"sealed":false'*) echo ok ;;
    *) echo nieuw ;;
  esac
}

kluis_inrichten() {
  docker compose up -d kluis >/dev/null
  [ "$(kluis_stand)" = nieuw ] || stop "De kluis is al ingericht. Ontzegelen: sudo ./bron.sh kluis-ontzegel"
  # Eén ontzegelsleutel: een PoC. In productie 3 van 5, en automatisch ontzegelen met een HSM of KMS.
  local uit ontzegel root
  uit="$(bao operator init -key-shares=1 -key-threshold=1 -format=json | tr -d '\n')"
  ontzegel="$(echo "$uit" | sed -n 's/.*"unseal_keys_b64": *\[ *"\([^"]*\)".*/\1/p')"
  root="$(echo "$uit" | sed -n 's/.*"root_token": *"\([^"]*\)".*/\1/p')"
  [ -n "$ontzegel" ] && [ -n "$root" ] || stop "Initialiseren mislukt."
  bao operator unseal "$ontzegel" >/dev/null
  baor() { docker compose exec -T -e BAO_TOKEN="$root" kluis bao "$@"; }
  baor secrets enable transit >/dev/null
  # De sleutel voor de HMAC: niet te exporteren, niet te verwijderen.
  baor write -f transit/keys/kluis-bsn type=aes256-gcm96 >/dev/null
  baor policy write kluis-hmac /openbao/beleid/beleid-hmac.hcl >/dev/null
  token() { baor token create -policy=kluis-hmac -period=768h -orphan -display-name="$1" -format=json \
              | tr -d '\n' | sed -n 's/.*"client_token": *"\([^"]*\)".*/\1/p'; }
  local ingestie portaal
  ingestie="$(token df-ingestie)"; portaal="$(token df-portaal)"
  [ -n "$ingestie" ] && [ -n "$portaal" ] || stop "Tokens maken mislukt."
  baor token revoke -self >/dev/null
  cat <<UIT

  De kluis is ingericht. Bewaar dit nu in je wachtwoordmanager, buiten deze server;
  het wordt nergens bewaard.

    Ontzegelsleutel:    $ontzegel
        (na elke herstart van dfw of van de kluis: sudo ./bron.sh kluis-ontzegel)

  Voor dfc (installeer-platform.sh vraagt erom):
    Token ingestie:     $ingestie
    Token portaal:      $portaal

  Het root-token is ingetrokken. Een nieuw maken kan met de ontzegelsleutel
  (bao operator generate-root).

UIT
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
  kluis-inrichten) maak_env; kluis_inrichten ;;
  kluis-ontzegel)
    docker compose up -d kluis >/dev/null
    [ "$(kluis_stand)" = verzegeld ] || { ok "De kluis is niet verzegeld ($(kluis_stand))"; exit 0; }
    read -r -s -p "  Ontzegelsleutel: " K; echo
    bao operator unseal "$K" >/dev/null || stop "Ontzegelen mislukt."
    ok "De kluis is ontzegeld" ;;
  kluis-status) echo "  kluis: $(kluis_stand)" ;;
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
  *) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
