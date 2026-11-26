# Gedeelde hulpfuncties voor de serverscripts. Wordt ingelezen, niet gestart.
# Overgenomen uit oa-uitrol (server/lib.sh) en ingekort voor twee servers.
# shellcheck shell=bash

set -euo pipefail

DF_MAP="${DF_MAP:-/etc/datafundament}"
WG_MAP="${WG_MAP:-/etc/wireguard}"
DF_REPO="${DF_REPO:-/opt/datafundament}"
# Eigen WireGuard-netwerk; 10.66.0.0/24 is van de Office Assistent.
WG_NET="10.67.0"
# shellcheck disable=SC2034  # gebruikt in de scripts die dit inlezen
WG_POORT=51820
# shellcheck disable=SC2034
ROLLEN=(platform bron)

meld()     { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()       { printf '  \033[32m✓\033[0m %s\n' "$*"; }
waarschuw(){ printf '  \033[33m!\033[0m %s\n' "$*"; }
stop()     { printf '\n\033[1;31mGestopt:\033[0m %s\n\n' "$*" >&2; exit 1; }

moet_root() {
  [ "$(id -u)" -eq 0 ] || stop "Start dit script met sudo ervoor, bijvoorbeeld: sudo $0"
}

# De rollen (DF-ADR-009):
#   platform = dfc (Datafundament Core): het lakehouse, met Caddy; 10.67.0.1
#   bron     = dfw: het bronsysteem met de testdata van VrijBRP;   10.67.0.2
wg_nr() {
  case "$1" in platform) echo 1 ;; bron) echo 2 ;; *) stop "Onbekende rol: $1" ;; esac
}
wg_ip() { echo "$WG_NET.$(wg_nr "$1")"; }

server_naam() {
  case "$1" in platform) echo "dfc (platform)" ;; bron) echo "dfw (bron)" ;; *) echo "$1" ;; esac
}

hostnaam() {
  case "$1" in platform) echo dfc ;; bron) echo dfw ;; esac
}

rol() {
  [ -s "$DF_MAP/rol" ] || stop "Deze server heeft nog geen rol. Begin met inrichten.sh."
  cat "$DF_MAP/rol"
}

# Het publieke IPv4-adres: het bronadres van de route naar buiten.
publiek_ip() {
  ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit }}'
}

# Het adres waarover WireGuard loopt: het adres in het privénetwerk van de
# provider als dat er is, anders het publieke. Docker-, WireGuard- en
# veth-kaarten tellen niet mee.
koppel_ip() {
  local p
  p="$(ip -4 -o addr show scope global 2>/dev/null \
    | awk '$2 !~ /^(docker|br-|veth|wg|lo)/ {split($4, a, "/"); print a[1]}' \
    | grep -E '^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)' | grep -v "^$WG_NET\." | head -1 || true)"
  echo "${p:-$(publiek_ip)}"
}

vraag_ja() {
  local a
  read -r -p "$1 [ja/nee] " a
  [[ "${a,,}" =~ ^(j|ja|y|yes)$ ]]
}

# Willekeurig geheim, alleen hexadecimale tekens: veilig in .env, JSON en URL's.
geheim() { openssl rand -hex "${1:-32}"; }

# Leest een KEY=waarde-bestand zonder het als script uit te voeren.
lees_env() {
  local bestand="$1" regel naam waarde
  [ -f "$bestand" ] || return 0
  while IFS= read -r regel || [ -n "$regel" ]; do
    regel="${regel%$'\r'}"
    [[ -z "$regel" || "$regel" == \#* ]] && continue
    [[ "$regel" =~ ^([A-Z][A-Z0-9_]*)=([A-Za-z0-9+/=.:_,@-]*)$ ]] || stop "Onverwachte regel in $bestand: $regel"
    naam="${BASH_REMATCH[1]}"
    waarde="${BASH_REMATCH[2]}"
    printf -v "$naam" '%s' "$waarde"
    export "${naam?}"
  done < "$bestand"
}

geldig_ip()  { [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }
geldige_wg() { [[ "$1" =~ ^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=$ ]]; }
