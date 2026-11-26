#!/usr/bin/env bash
# INRICHTING.md stap 5 — dfc en dfw koppelen met WireGuard: een versleuteld
# netwerk 10.67.0.0/24 over het privénetwerk van de provider.
#
#   Op dfc:  sudo /opt/datafundament/server/koppelen.sh   → plak de koppelregel van dfw
#   Op dfw:  sudo /opt/datafundament/server/koppelen.sh   → plak de koppelregel van dfc
#
# De koppelregels bevatten alleen publieke sleutels; er gaan geen geheimen
# tussen de servers heen en weer. Opnieuw draaien kan; dan plak je opnieuw.

HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$HIER/lib.sh"
moet_root

ROL="$(rol)"
case "$ROL" in platform) ANDER=bron ;; bron) ANDER=platform ;; esac
EIGEN_SLEUTEL="$(cat "$WG_MAP/df.pub" 2>/dev/null)" || stop "Geen WireGuard-sleutel. Draai eerst inrichten.sh."
EIGEN_IP="$(koppel_ip)"
PEER="$DF_MAP/peer.env"

meld "Koppelen op $(server_naam "$ROL")"
echo "  Deze server: $EIGEN_IP, WireGuard-adres $(wg_ip "$ROL")"
echo "  Plak de koppelregel van $(server_naam "$ANDER") (begint met DF-KOPPEL $ANDER)."
while :; do
  read -r regel || stop "Invoer afgebroken"
  regel="${regel%$'\r'}"
  read -r woord r ip sleutel _ <<<"$regel" || true
  [ "${woord:-}" = DF-KOPPEL ] || { [ -n "$regel" ] && waarschuw "Dat is geen koppelregel."; continue; }
  if [ "$r" = "$ROL" ]; then waarschuw "Dat is de regel van deze server zelf. Plak die van $(server_naam "$ANDER")."; continue; fi
  [ "$r" = "$ANDER" ] || { waarschuw "Onbekende rol in: $regel"; continue; }
  geldig_ip "$ip" && geldige_wg "$sleutel" || { waarschuw "Deze regel klopt niet, plak hem opnieuw."; continue; }
  [ "$sleutel" != "$EIGEN_SLEUTEL" ] || { waarschuw "Dat is de sleutel van deze server zelf."; continue; }
  break
done

umask 077
cat > "$PEER" <<EOF
PEER_ROL=$ANDER
PEER_IP=$ip
PEER_SLEUTEL=$sleutel
EOF
cat > "$WG_MAP/wg0.conf" <<EOF
# Datafundament — versleuteld netwerk tussen dfc en dfw (DF-ADR-009)
[Interface]
Address = $(wg_ip "$ROL")/24
ListenPort = $WG_POORT
PrivateKey = $(cat "$WG_MAP/df.key")

# $(server_naam "$ANDER")
[Peer]
PublicKey = $sleutel
Endpoint = $ip:$WG_POORT
AllowedIPs = $(wg_ip "$ANDER")/32
PersistentKeepalive = 25
EOF
umask 022

# WireGuard alleen open voor de andere server, en alleen op het adres in het
# privénetwerk (of het publieke adres als er geen privénetwerk is).
ufw allow from "$ip" to "$EIGEN_IP" port "$WG_POORT" proto udp comment "WireGuard $(server_naam "$ANDER")" >/dev/null
systemctl enable wg-quick@wg0 >/dev/null 2>&1
systemctl restart wg-quick@wg0
ok "WireGuard draait: dit is $(wg_ip "$ROL"), de andere server is $(wg_ip "$ANDER")"

if ping -c 2 -W 2 "$(wg_ip "$ANDER")" >/dev/null 2>&1; then
  ok "$(server_naam "$ANDER") is bereikbaar via $(wg_ip "$ANDER")"
else
  waarschuw "$(server_naam "$ANDER") ($(wg_ip "$ANDER")) is nog niet bereikbaar."
  echo "  Dat is normaal zolang je de andere server nog niet hebt gekoppeld. Test daarna: sudo $DF_REPO/server/controleer.sh"
fi
echo
