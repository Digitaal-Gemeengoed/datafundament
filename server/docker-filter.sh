#!/usr/bin/env bash
# Filter voor de poorten die containers publiceren (keten DOCKER-USER).
# Overgenomen uit oa-uitrol.
#
# Docker opent gepubliceerde poorten buiten ufw om. De compose-bestanden
# binden interne diensten aan het WireGuard-adres of aan 127.0.0.1; dit filter
# maakt het strikt: een containerpoort op het WireGuard-adres is alleen
# bereikbaar via wg0, en alleen voor de server die hem nodig heeft.
#
#   platform (dfc, 10.67.0.1): 3900 (Garage, landingsbucket) ← bron; 80/443 (Caddy) zijn publiek
#   bron     (dfw, 10.67.0.2): 5432 (PostgreSQL van de bron, voor dlt en CDC) ← platform
#                              8000 (Zaken-API) ← platform
#
# Draait vóór Docker start (df-docker-filter.service); Docker laat de keten
# DOCKER-USER zelf ongemoeid.
set -euo pipefail

ROL="${1:-$(cat "${DF_MAP:-/etc/datafundament}/rol")}"
NET=10.67.0
case "$ROL" in
  platform) EIGEN=$NET.1; TOEGESTAAN=("$NET.2 3900") ;;
  bron)     EIGEN=$NET.2; TOEGESTAAN=("$NET.1 5432" "$NET.1 8000") ;;
  *) echo "Onbekende rol: $ROL" >&2; exit 1 ;;
esac

ipt() { iptables -w "$@"; }

ipt -N DOCKER-USER 2>/dev/null || true
ipt -F DOCKER-USER
# Antwoorden op verbindingen die al bestaan (ook die de containers zelf opzetten).
ipt -A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
for regel in "${TOEGESTAAN[@]}"; do
  read -r bron poort <<<"$regel"
  ipt -A DOCKER-USER -i wg0 -s "$bron" -p tcp -m conntrack --ctorigdst "$EIGEN" --ctorigdstport "$poort" -j RETURN
done
# Al het andere dat via WireGuard binnenkomt: weg.
ipt -A DOCKER-USER -i wg0 -j DROP
# Wie het WireGuard-adres via een andere netwerkkaart probeert: weg.
ipt -A DOCKER-USER -m conntrack --ctorigdst "$EIGEN" -j DROP
ipt -A DOCKER-USER -j RETURN
