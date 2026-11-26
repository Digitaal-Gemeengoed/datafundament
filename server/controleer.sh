#!/usr/bin/env bash
# Controleert de basis van een server: rol, SSH, firewall, WireGuard, Docker
# en het poortfilter. Verandert niets.
#
#   sudo /opt/datafundament/server/controleer.sh

HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$HIER/lib.sh"
moet_root

FOUT=0
mis() { waarschuw "$*"; FOUT=1; }

ROL="$(rol)"
case "$ROL" in platform) ANDER=bron ;; bron) ANDER=platform ;; esac
meld "Controle van $(server_naam "$ROL") ($(hostname))"

# SSH
SSHD="$(sshd -T 2>/dev/null || true)"
if grep -qx "passwordauthentication no" <<<"$SSHD" && grep -qx "permitrootlogin no" <<<"$SSHD"; then
  ok "SSH: alleen sleutels, geen root"
else
  mis "SSH staat nog open voor wachtwoorden of root. Draai ssh-afsluiten.sh."
fi

# Firewall
UFW="$(ufw status 2>/dev/null || true)"
if grep -q "Status: active" <<<"$UFW"; then
  ok "Firewall staat aan"
  if [ "$ROL" = bron ] && grep -qE '^(80|443)/tcp' <<<"$UFW"; then
    mis "Op de bron staan HTTP of HTTPS open; dat hoort niet."
  fi
else
  mis "De firewall staat uit."
fi

# WireGuard
if systemctl is-active --quiet wg-quick@wg0; then
  ok "WireGuard draait ($(wg_ip "$ROL"))"
  if ping -c 2 -W 2 "$(wg_ip "$ANDER")" >/dev/null 2>&1; then
    ok "$(server_naam "$ANDER") bereikbaar via $(wg_ip "$ANDER")"
  else
    mis "$(server_naam "$ANDER") ($(wg_ip "$ANDER")) niet bereikbaar via WireGuard."
  fi
else
  mis "WireGuard draait niet. Draai koppelen.sh."
fi

# Docker en filter
if docker info >/dev/null 2>&1; then
  ok "Docker $(docker version --format '{{.Server.Version}}') draait"
else
  mis "Docker draait niet."
fi
if iptables -w -S DOCKER-USER 2>/dev/null | grep -q -- "-i wg0 -j DROP"; then
  ok "Poortfilter voor containers staat"
else
  mis "Het poortfilter voor containers ontbreekt. Start: sudo systemctl restart df-docker-filter"
fi

echo
if [ "$FOUT" = 0 ]; then ok "Alles in orde"; else waarschuw "Er zijn punten om na te lopen (zie hierboven)."; fi
echo
exit "$FOUT"
