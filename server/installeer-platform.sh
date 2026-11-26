#!/usr/bin/env bash
# Het platform op dfc installeren of bijwerken (DF-ADR-009). Opnieuw draaien kan:
# geheimen en data blijven, nieuwe code en instellingen worden doorgevoerd.
#
#   sudo /opt/datafundament/server/installeer-platform.sh
#
# Eerste keer: vraagt het wachtwoord van dlt_lezer (op dfw: sudo ./bron.sh dlt-wachtwoord)
# en maakt een wachtwoord voor de websites.

HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$HIER/lib.sh"
moet_root
[ "$(rol)" = platform ] || stop "Dit script is voor dfc (platform). Op dfw: /opt/datafundament/bron/bron.sh"

cd "$DF_REPO/compose" || stop "Map $DF_REPO/compose ontbreekt."
ENV=.env
waarde() { grep -m1 "^$1=" "$ENV" 2>/dev/null | cut -d= -f2- | sed "s/^'//; s/'$//"; }
vul_aan() {  # NAAM WAARDE: alleen als NAAM nog niet in .env staat
  grep -q "^$1=" "$ENV" 2>/dev/null && return 0
  printf '%s=%s\n' "$1" "$2" >> "$ENV"
}

meld "Instellingen en geheimen ($DF_REPO/compose/.env)"
umask 077; touch "$ENV"; umask 022; chmod 600 "$ENV"
vul_aan DOMEIN datafundament.haarlem.dev
for n in DB_WACHTWOORD LK_DB_WACHTWOORD DAGSTER_DB_WACHTWOORD DWH_SCHRIJVER_WACHTWOORD DWH_LEZER_WACHTWOORD; do
  vul_aan "$n" "$(geheim 24)"
done
vul_aan LK_SLEUTEL "$(geheim 32)"
vul_aan GARAGE_RPC_GEHEIM "$(geheim 32)"
for k in BEHEER LAKEKEEPER SCHRIJVER LEZER; do
  vul_aan "GARAGE_${k}_SLEUTEL" "GK$(geheim 12)"
  vul_aan "GARAGE_${k}_GEHEIM" "$(geheim 32)"
done
if ! grep -q '^DLT_WACHTWOORD=' "$ENV"; then
  while :; do
    read -r -s -p "  Wachtwoord van dlt_lezer (op dfw: sudo ./bron.sh dlt-wachtwoord): " W; echo
    [[ "$W" =~ ^[0-9a-f]{16,}$ ]] && break
    waarschuw "Dat lijkt niet op het wachtwoord (alleen 0-9 en a-f)."
  done
  vul_aan DLT_WACHTWOORD "$W"
fi
vul_aan WEB_GEBRUIKER datafundament
if ! grep -q '^WEB_WACHTWOORD=' "$ENV"; then
  WW="$(geheim 12)"
  HASH="$(docker run --rm caddy:2.10 caddy hash-password --plaintext "$WW")"
  vul_aan WEB_WACHTWOORD "$WW"
  # Tussen enkele aanhalingstekens: de hash bevat $-tekens.
  vul_aan WEB_WACHTWOORD_HASH "'$HASH'"
fi
ok "Alle instellingen staan in .env (alleen leesbaar voor root)"

if ping -c 1 -W 2 10.67.0.2 >/dev/null 2>&1; then
  ok "De bron op dfw is bereikbaar via WireGuard"
else
  waarschuw "dfw (10.67.0.2) is niet bereikbaar; de ingestie werkt pas als de koppeling er is."
fi

meld "Images ophalen en de code bouwen (eerste keer: een paar minuten)"
docker compose build -q werk
docker compose pull -q --ignore-buildable db garage lakekeeper lakekeeper-migratie trino caddy
ok "Klaar"

meld "Database en opslag"
docker compose up -d --wait db garage
for _ in $(seq 1 30); do
  docker compose exec -T garage /garage status >/dev/null 2>&1 && break
  sleep 2
done
garage() { docker compose exec -T garage /garage "$@"; }
# Een eigen sleutel per onderdeel (DF-ADR-002): Lakekeeper en de schrijvers lezen
# en schrijven, Trino leest alleen.
sleutel() {  # NAAM RECHTEN...
  local naam="$1"; shift
  local id geheim
  id="$(waarde "GARAGE_${naam^^}_SLEUTEL")"; geheim="$(waarde "GARAGE_${naam^^}_GEHEIM")"
  if ! garage key info "$naam" >/dev/null 2>&1; then
    garage key import --yes "$id" "$geheim" -n "$naam" >/dev/null \
      || stop "Sleutel '$naam' kon niet in Garage worden gezet. Zie: sudo docker compose -f $DF_REPO/compose/compose.yml logs garage"
  fi
  garage bucket allow "$@" lakehouse --key "$naam" >/dev/null \
    || stop "Rechten voor sleutel '$naam' op de bucket lakehouse konden niet worden gezet."
  ok "Sleutel $naam: ${*//--/}"
}
sleutel lakekeeper --read --write
sleutel schrijver --read --write
sleutel lezer --read

meld "Iceberg-catalogus (Lakekeeper)"
docker compose up -d lakekeeper
docker compose run --rm --no-deps -T \
  -e GARAGE_LAKEKEEPER_SLEUTEL="$(waarde GARAGE_LAKEKEEPER_SLEUTEL)" \
  -e GARAGE_LAKEKEEPER_GEHEIM="$(waarde GARAGE_LAKEKEEPER_GEHEIM)" \
  werk python -m beheer.inrichten

meld "De rest: Trino, Dagster, Caddy"
docker compose up -d --remove-orphans
ok "Alles draait. Caddy haalt bij de eerste aanvraag per naam een certificaat op."

D="$(waarde DOMEIN)"
cat <<EOF

  Startpagina:  https://$D/
  Dagster:      https://dagster.$D/
  Lakekeeper:   https://catalogus.$D/ui/
  Trino:        https://trino.$D/ui/
                JDBC: jdbc:trino://trino.$D:443?SSL=true

  Gebruiker:    $(waarde WEB_GEBRUIKER)
  Wachtwoord:   $(waarde WEB_WACHTWOORD)
  (Bewaar het in je wachtwoordmanager. Opnieuw tonen: sudo grep WEB_WACHTWOORD= $DF_REPO/compose/.env)

  De ingestie van de bron draait elke 5 minuten (Dagster, schema ingestie_elke_5_minuten).
  Controleren: sudo docker compose -f $DF_REPO/compose/compose.yml ps
EOF
echo
