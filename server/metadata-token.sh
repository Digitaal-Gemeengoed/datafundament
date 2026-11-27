#!/usr/bin/env bash
# Het token van de ingestion-bot van OpenMetadata opslaan, voor de job metadata in
# Dagster (DF-ADR-007). Eén keer, na de eerste inlog op OpenMetadata als beheerder:
# Settings → Bots → ingestion-bot → token kopiëren.
#
#   sudo /opt/datafundament/server/metadata-token.sh
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$HIER/lib.sh"
moet_root
[ "$(rol)" = platform ] || stop "OpenMetadata draait op dfc (platform)."
cd "$DF_REPO/compose" || exit 1

read -r -s -p "  Token van de ingestion-bot: " T; echo
[[ "$T" =~ ^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$ ]] || stop "Dat lijkt niet op een token (JWT)."

# Neemt OpenMetadata het aan? Gevraagd vanuit de werk-container, zoals de job het doet.
docker compose exec -T werk python - "$T" <<'PY' || stop "OpenMetadata neemt dit token niet aan (of draait niet)."
import sys, urllib.request
r = urllib.request.Request("http://openmetadata:8585/api/v1/users/loggedInUser",
                           headers={"Authorization": "Bearer " + sys.argv[1]})
urllib.request.urlopen(r, timeout=10)
PY

sed -i '/^OPENMETADATA_BOT_TOKEN=/d' .env
printf 'OPENMETADATA_BOT_TOKEN=%s\n' "$T" >> .env
docker compose up -d werk dagster-webserver dagster-daemon >/dev/null
ok "Token opgeslagen. De job metadata draait na de volgende geslaagde keten (hoogstens één keer per uur)."
