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
for n in DB_WACHTWOORD LK_DB_WACHTWOORD DAGSTER_DB_WACHTWOORD DWH_SCHRIJVER_WACHTWOORD DWH_LEZER_WACHTWOORD \
         KC_DB_WACHTWOORD KC_BEHEERDER_WACHTWOORD PORTAAL_DB_WACHTWOORD PORTAAL_APP_WACHTWOORD KLUIS_DB_WACHTWOORD \
         OM_DB_WACHTWOORD TRINO_OM_WACHTWOORD; do
  vul_aan "$n" "$(geheim 24)"
done
vul_aan LK_SLEUTEL "$(geheim 32)"
vul_aan PORTAAL_ADMIN_GEHEIM "$(geheim 32)"
# Trino levert elke datavraag af bij het portaal, met dit token (DF-ADR-016).
vul_aan DATAVRAGEN_TOKEN "$(geheim 32)"
vul_aan GARAGE_RPC_GEHEIM "$(geheim 32)"
# OpenMetadata (DF-ADR-007): een eigen Fernet-sleutel en sleutel-id voor de tokens.
vul_aan OM_FERNET_SLEUTEL "$(openssl rand -base64 32 | tr '+/' '-_')"
vul_aan OM_JWT_SLEUTEL_ID "$(geheim 16)"
# Trino (DF-ADR-017): de sleutel tussen de onderdelen van Trino.
vul_aan TRINO_INTERN_GEHEIM "$(geheim 32)"
for k in BEHEER LAKEKEEPER SCHRIJVER LEZER LANDING; do
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
if ! grep -q '^ZAKEN_API_GEHEIM=' "$ENV"; then
  while :; do
    read -r -s -p "  Geheim van de Zaken-API (op dfw: sudo ./bron.sh zaken-api-geheim): " W; echo
    [[ "$W" =~ ^[0-9a-f]{32,}$ ]] && break
    waarschuw "Dat lijkt niet op het geheim (alleen 0-9 en a-f)."
  done
  vul_aan ZAKEN_API_GEHEIM "$W"
fi
# De kluis (DF-ADR-015): tokens voor OpenBao op dfw, alleen om een HMAC te laten berekenen.
for wie in INGESTIE PORTAAL; do
  if ! grep -q "^KLUIS_BAO_TOKEN_$wie=" "$ENV"; then
    while :; do
      read -r -s -p "  Token van de kluis voor ${wie,,} (op dfw: sudo ./bron.sh kluis-inrichten): " W; echo
      [[ "$W" =~ ^[A-Za-z0-9._-]{20,}$ ]] && break
      waarschuw "Dat lijkt niet op een token van OpenBao."
    done
    vul_aan "KLUIS_BAO_TOKEN_$wie" "$W"
  fi
done
vul_aan WEB_GEBRUIKER datafundament
if ! grep -q '^WEB_WACHTWOORD=' "$ENV"; then
  WW="$(geheim 12)"
  HASH="$(docker run --rm caddy:2.10 caddy hash-password --plaintext "$WW")"
  vul_aan WEB_WACHTWOORD "$WW"
  # Tussen enkele aanhalingstekens: de hash bevat $-tekens.
  vul_aan WEB_WACHTWOORD_HASH "'$HASH'"
fi
ok "Alle instellingen staan in .env (alleen leesbaar voor root)"

# OpenMetadata tekent zijn tokens met een RSA-sleutel. Die in het image is openbaar;
# hier een eigen, alleen leesbaar voor de gebruiker in de container (65532).
OMS="$DF_REPO/compose/openmetadata"
if [ ! -f "$OMS/private_key.der" ]; then
  install -d -m 700 "$OMS"
  T="$(mktemp)"
  openssl genrsa -out "$T" 2048 2>/dev/null
  openssl pkcs8 -topk8 -inform PEM -outform DER -nocrypt -in "$T" -out "$OMS/private_key.der"
  openssl rsa -in "$T" -pubout -outform DER -out "$OMS/public_key.der" 2>/dev/null
  shred -u "$T" 2>/dev/null || rm -f "$T"
  ok "Eigen RSA-sleutels voor OpenMetadata"
fi
chown -R 65532:65532 "$OMS"; chmod 700 "$OMS"; chmod 400 "$OMS"/*.der
# Trino (DF-ADR-017): de regels schrijft het portaal (uid 1000, net als Trino); tot
# dan mag niemand iets. Het wachtwoord van de dienstgebruiker openmetadata (bcrypt).
TR="$DF_REPO/compose/trino"
install -d -m 755 -o 1000 -g 1000 "$TR/regels" "$TR/wachtwoorden"
[ -f "$TR/regels/rules.json" ] || printf '{"catalogs": [{"allow": "none"}], "tables": [{"privileges": []}]}\n' > "$TR/regels/rules.json"
chown 1000:1000 "$TR/regels/rules.json"
if [ ! -s "$TR/wachtwoorden/wachtwoorden.db" ]; then
  docker run --rm httpd:2.4-alpine htpasswd -nbBC 10 openmetadata "$(waarde TRINO_OM_WACHTWOORD)" \
    | sed '/^$/d' > "$TR/wachtwoorden/wachtwoorden.db"
  chown 1000:1000 "$TR/wachtwoorden/wachtwoorden.db"; chmod 400 "$TR/wachtwoorden/wachtwoorden.db"
  ok "Wachtwoord voor de dienstgebruiker openmetadata in Trino"
fi

# OpenSearch (de zoekindex van OpenMetadata) vraagt meer geheugenkaarten.
if [ "$(sysctl -n vm.max_map_count)" -lt 262144 ]; then
  echo "vm.max_map_count=262144" > /etc/sysctl.d/90-datafundament.conf
  sysctl -q -p /etc/sysctl.d/90-datafundament.conf
  ok "vm.max_map_count op 262144 (voor OpenSearch)"
fi

# Het poortfilter bijwerken (nieuwe poorten, zoals Garage voor de landingsbucket).
if [ -x /usr/local/sbin/df-docker-filter ] && ! cmp -s "$DF_REPO/server/docker-filter.sh" /usr/local/sbin/df-docker-filter; then
  install -m 755 "$DF_REPO/server/docker-filter.sh" /usr/local/sbin/df-docker-filter
  systemctl restart df-docker-filter
  ok "Poortfilter bijgewerkt"
fi

if curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://10.67.0.2:8200/v1/sys/health | grep -q 200; then
  ok "De kluis (OpenBao op dfw) is bereikbaar en ontzegeld"
else
  waarschuw "De kluis op dfw is niet bereikbaar of verzegeld; de ingestie en verwijderverzoeken wachten daarop (op dfw: sudo ./bron.sh kluis-status)."
fi

if ping -c 1 -W 2 10.67.0.2 >/dev/null 2>&1; then
  ok "De bron op dfw is bereikbaar via WireGuard"
else
  waarschuw "dfw (10.67.0.2) is niet bereikbaar; de ingestie werkt pas als de koppeling er is."
fi

meld "Images ophalen en de code bouwen (eerste keer: een paar minuten)"
docker compose build -q werk portaal-migreer
docker compose pull -q --ignore-buildable db garage lakekeeper lakekeeper-migratie trino caddy keycloak \
  zoekindex openmetadata openmetadata-migratie
ok "Klaar"

meld "Database en opslag"
docker compose up -d --wait db garage
for _ in $(seq 1 30); do
  docker compose exec -T garage /garage status >/dev/null 2>&1 && break
  sleep 2
done
# Databases die later bijkwamen (Keycloak, portaal, kluis): ook in een bestaande installatie.
psql_beheer() { docker compose exec -T db psql -v ON_ERROR_STOP=1 -U beheer -d postgres -q "$@"; }
rol() {  # ROL WACHTWOORD: aanmaken als hij er niet is; het wachtwoord altijd zetten
  psql_beheer -v rol="$1" -v ww="$2" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN', :'rol') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'rol') \gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'rol', :'ww') \gexec
EOSQL
}
database() {  # DATABASE EIGENAAR
  psql_beheer -v db="$1" -v rol="$2" <<'EOSQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'rol') WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'db') \gexec
EOSQL
}
rol keycloak "$(waarde KC_DB_WACHTWOORD)";          database keycloak keycloak
rol df_portaal "$(waarde PORTAAL_DB_WACHTWOORD)";   database df_portaal df_portaal
rol df_portaal_app "$(waarde PORTAAL_APP_WACHTWOORD)"
psql_beheer -c "GRANT CONNECT ON DATABASE df_portaal TO df_portaal, df_portaal_app"
rol kluis "$(waarde KLUIS_DB_WACHTWOORD)";          database kluis kluis
rol openmetadata "$(waarde OM_DB_WACHTWOORD)";       database openmetadata openmetadata
psql_beheer -c "ALTER ROLE openmetadata SET work_mem = '10MB'"
ok "Databases voor Keycloak, het portaal, de kluis en OpenMetadata"

garage() { docker compose exec -T garage /garage "$@"; }
# Een eigen sleutel per onderdeel (DF-ADR-002): Lakekeeper en de schrijvers lezen
# en schrijven, Trino leest alleen.
sleutel() {  # NAAM BUCKET RECHTEN...
  local naam="$1" bucket="$2"; shift 2
  local id geheim
  id="$(waarde "GARAGE_${naam^^}_SLEUTEL")"; geheim="$(waarde "GARAGE_${naam^^}_GEHEIM")"
  if ! garage key info "$naam" >/dev/null 2>&1; then
    garage key import --yes "$id" "$geheim" -n "$naam" >/dev/null \
      || stop "Sleutel '$naam' kon niet in Garage worden gezet. Zie: sudo docker compose -f $DF_REPO/compose/compose.yml logs garage"
  fi
  garage bucket allow "$@" "$bucket" --key "$naam" >/dev/null \
    || stop "Rechten voor sleutel '$naam' op de bucket $bucket konden niet worden gezet."
  ok "Sleutel $naam op $bucket: ${*//--/}"
}
sleutel lakekeeper lakehouse --read --write
sleutel schrijver lakehouse --read --write
sleutel lezer lakehouse --read
# De landingsbucket (DF-ADR-014): de leverancier op dfw mag er alleen in schrijven,
# de ingestie leest hem.
garage bucket info landing >/dev/null 2>&1 || garage bucket create landing >/dev/null \
  || stop "De bucket landing kon niet worden gemaakt."
sleutel landing landing --write
sleutel schrijver landing --read

meld "Iceberg-catalogus (Lakekeeper)"
docker compose up -d lakekeeper
docker compose run --rm --no-deps -T \
  -e GARAGE_LAKEKEEPER_SLEUTEL="$(waarde GARAGE_LAKEKEEPER_SLEUTEL)" \
  -e GARAGE_LAKEKEEPER_GEHEIM="$(waarde GARAGE_LAKEKEEPER_GEHEIM)" \
  werk python -m beheer.inrichten

meld "De rest: Trino, Dagster, Keycloak, portaal, OpenMetadata, Caddy"
docker compose up -d --remove-orphans
# Caddy en Trino krijgen losse configuratiebestanden. Na een git pull is dat een nieuw
# bestand, dat een draaiende container niet ziet: herstarten, dan lezen ze het opnieuw.
docker compose restart caddy trino >/dev/null
ok "Alles draait. Caddy haalt bij de eerste aanvraag per naam een certificaat op."

if [ -z "$(waarde PORTAAL_OIDC_GEHEIM)" ] || [ -z "$(waarde OM_OIDC_GEHEIM)" ] || [ -z "$(waarde TRINO_OIDC_GEHEIM)" ]; then
  "$DF_REPO/server/keycloak.sh"
fi

D="$(waarde DOMEIN)"
cat <<EOF

  Portaal:      https://admin.$D/   (inloggen via Keycloak; noodaccount op /emergency)
  Metadata:     https://metadata.$D/   (OpenMetadata; inloggen via Keycloak)
  Startpagina:  https://$D/
  Dagster:      https://dagster.$D/
  Lakekeeper:   https://catalogus.$D/ui/
  Trino:        https://trino.$D/ui/   (inloggen via Keycloak)
                JDBC: jdbc:trino://trino.$D:443?SSL=true&externalAuthentication=true

  Gebruiker:    $(waarde WEB_GEBRUIKER)
  Wachtwoord:   $(waarde WEB_WACHTWOORD)
  (Bewaar het in je wachtwoordmanager. Opnieuw tonen: sudo grep WEB_WACHTWOORD= $DF_REPO/compose/.env)

  De ingestie van de bronnen draait elke 5 minuten (Dagster, schema ingestie_elke_5_minuten).

  Noodaccount van het portaal instellen (eenmalig; toont wachtwoord en TOTP-geheim):
    sudo docker compose -f $DF_REPO/compose/compose.yml run --rm portaal-migreer node backend/dist/cli.js nood-instellen

  Sleutel voor de landingsbucket, voor dfw (sudo ./bron.sh landing-sleutel):
    Sleutel-id: $(waarde GARAGE_LANDING_SLEUTEL)
    Geheim:     opnieuw tonen met: sudo grep GARAGE_LANDING_GEHEIM= $DF_REPO/compose/.env
  Controleren: sudo docker compose -f $DF_REPO/compose/compose.yml ps
EOF
if [ -z "$(waarde OPENMETADATA_BOT_TOKEN)" ]; then
  cat <<EOF

  OpenMetadata wordt nog niet bijgewerkt. Log in op https://metadata.$D/ (als
  $(waarde OM_BEHEERDER)), ga naar Settings → Bots → ingestion-bot, kopieer het token en:
    sudo $DF_REPO/server/metadata-token.sh
EOF
fi
echo
