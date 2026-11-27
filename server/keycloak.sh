#!/usr/bin/env bash
# Keycloak inrichten voor het Datafundament (DF-ADR-012). Op dfc, na
# installeer-platform.sh (dat roept dit ook zelf aan als het nog niet is gebeurd).
# Mag vaker worden gestart; wat er al is, blijft staan. Naar het voorbeeld van
# server/keycloak-beheer.sh in oa-uitrol.
#
#   sudo /opt/datafundament/server/keycloak.sh
#
# Doet:
#   - realm 'datafundament', met brute-force-detectie;
#   - een vertrouwelijke client 'df-portaal' (authorization code + PKCE);
#   - een vertrouwelijke client 'df-metadata' voor OpenMetadata (DF-ADR-007);
#   - een vertrouwelijke client 'df-trino' voor Trino, met df-trino als audience
#     in het access token (DF-ADR-017);
#   - de AMR-mapper, zodat het id_token meldt dat er een tweede factor was;
#   - op de OTP-stap van de inlogflow de referentiewaarde 'otp';
#   - op verzoek een gebruiker voor jezelf (e-mail geverifieerd; bij de eerste
#     inlog een eigen wachtwoord en een authenticator-app);
#   - zet de client-geheimen en de uitgever in compose/.env, en de beheerder
#     van OpenMetadata (het deel vóór de @ van jouw e-mailadres).

HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
. "$HIER/lib.sh"
moet_root
[ "$(rol)" = platform ] || stop "Keycloak draait op dfc (platform)."
cd "$DF_REPO/compose" || exit 1
command -v jq >/dev/null || apt-get install -y -qq jq >/dev/null
ENV=.env
waarde() { grep -m1 "^$1=" "$ENV" | cut -d= -f2- | sed "s/^'//; s/'$//"; }
zet() {  # NAAM WAARDE: vervangen of toevoegen
  sed -i "/^$1=/d" "$ENV"
  printf '%s=%s\n' "$1" "$2" >> "$ENV"
}
DOMEIN="$(waarde DOMEIN)"
PORTAAL="https://admin.$DOMEIN"
R=datafundament

kc() { docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/df-kcadm.config; }

meld "Keycloak ($PORTAAL, https://id.$DOMEIN)"
for _ in $(seq 1 60); do
  kc config credentials --server http://localhost:8080 --realm master --user beheer \
    --password "$(waarde KC_BEHEERDER_WACHTWOORD)" >/dev/null 2>&1 && break
  sleep 3
done
kc get realms/master --fields realm >/dev/null 2>&1 \
  || stop "Inloggen op Keycloak lukte niet. Draait hij? sudo docker compose -f $DF_REPO/compose/compose.yml logs keycloak"
ok "Ingelogd op Keycloak"

# --- Realm -------------------------------------------------------------------------
if kc get "realms/$R" >/dev/null 2>&1; then
  ok "Realm $R bestaat al"
else
  kc create realms -s realm=$R -s enabled=true -s displayName="Datafundament" \
    -s bruteForceProtected=true -s failureFactor=10 -s loginWithEmailAllowed=true \
    -s duplicateEmailsAllowed=false -s 'otpPolicyType=totp' -s 'otpPolicyPeriod=30' >/dev/null
  ok "Realm $R aangemaakt (brute-force-detectie aan)"
fi

# --- Client ------------------------------------------------------------------------
ID="$(kc get clients -r $R -q clientId=df-portaal --fields id 2>/dev/null | jq -r '.[0].id // empty')"
if [ -z "$ID" ]; then
  kc create clients -r $R \
    -s clientId=df-portaal -s name="Portaal Datafundament" -s enabled=true \
    -s protocol=openid-connect -s publicClient=false -s clientAuthenticatorType=client-secret \
    -s secret="$(geheim 32)" \
    -s standardFlowEnabled=true -s implicitFlowEnabled=false \
    -s directAccessGrantsEnabled=false -s serviceAccountsEnabled=false \
    -s "redirectUris=[\"$PORTAAL/api/auth/terug\"]" -s "webOrigins=[\"$PORTAAL\"]" -s "rootUrl=$PORTAAL" \
    -s "attributes.\"post.logout.redirect.uris\"=$PORTAAL/" \
    -s 'attributes."pkce.code.challenge.method"=S256' >/dev/null
  ID="$(kc get clients -r $R -q clientId=df-portaal --fields id | jq -r '.[0].id')"
  ok "Client df-portaal aangemaakt"
else
  # Adressen altijd bijwerken, zodat een nieuwe naam voor het portaal meteen werkt.
  kc update "clients/$ID" -r $R \
    -s "redirectUris=[\"$PORTAAL/api/auth/terug\"]" -s "webOrigins=[\"$PORTAAL\"]" -s "rootUrl=$PORTAAL" \
    -s "attributes.\"post.logout.redirect.uris\"=$PORTAAL/" >/dev/null
  ok "Client df-portaal bestaat al; adressen gezet op $PORTAAL"
fi

# --- Client voor OpenMetadata ----------------------------------------------------------
METADATA="https://metadata.$DOMEIN"
OMID="$(kc get clients -r $R -q clientId=df-metadata --fields id 2>/dev/null | jq -r '.[0].id // empty')"
if [ -z "$OMID" ]; then
  kc create clients -r $R \
    -s clientId=df-metadata -s name="OpenMetadata" -s enabled=true \
    -s protocol=openid-connect -s publicClient=false -s clientAuthenticatorType=client-secret \
    -s secret="$(geheim 32)" \
    -s standardFlowEnabled=true -s implicitFlowEnabled=false \
    -s directAccessGrantsEnabled=false -s serviceAccountsEnabled=false \
    -s "redirectUris=[\"$METADATA/callback\"]" -s "webOrigins=[\"$METADATA\"]" -s "rootUrl=$METADATA" \
    -s "attributes.\"post.logout.redirect.uris\"=$METADATA/*" >/dev/null
  OMID="$(kc get clients -r $R -q clientId=df-metadata --fields id | jq -r '.[0].id')"
  ok "Client df-metadata aangemaakt"
else
  kc update "clients/$OMID" -r $R \
    -s "redirectUris=[\"$METADATA/callback\"]" -s "webOrigins=[\"$METADATA\"]" -s "rootUrl=$METADATA" >/dev/null
  ok "Client df-metadata bestaat al; adressen gezet op $METADATA"
fi

# --- Client voor Trino --------------------------------------------------------------------
TRINO="https://trino.$DOMEIN"
TRID="$(kc get clients -r $R -q clientId=df-trino --fields id 2>/dev/null | jq -r '.[0].id // empty')"
if [ -z "$TRID" ]; then
  kc create clients -r $R \
    -s clientId=df-trino -s name="Trino" -s enabled=true \
    -s protocol=openid-connect -s publicClient=false -s clientAuthenticatorType=client-secret \
    -s secret="$(geheim 32)" \
    -s standardFlowEnabled=true -s implicitFlowEnabled=false \
    -s directAccessGrantsEnabled=false -s serviceAccountsEnabled=false \
    -s "redirectUris=[\"$TRINO/oauth2/callback\"]" -s "webOrigins=[\"$TRINO\"]" -s "rootUrl=$TRINO" \
    -s "attributes.\"post.logout.redirect.uris\"=$TRINO/ui/logout/logout.html" >/dev/null
  TRID="$(kc get clients -r $R -q clientId=df-trino --fields id | jq -r '.[0].id')"
  ok "Client df-trino aangemaakt"
else
  kc update "clients/$TRID" -r $R \
    -s "redirectUris=[\"$TRINO/oauth2/callback\"]" -s "webOrigins=[\"$TRINO\"]" -s "rootUrl=$TRINO" >/dev/null
  ok "Client df-trino bestaat al; adressen gezet op $TRINO"
fi
# Trino neemt alleen een access token aan met zijn eigen client-id als audience.
if kc get "clients/$TRID/protocol-mappers/models" -r $R | jq -e '.[] | select(.protocolMapper == "oidc-audience-mapper")' >/dev/null; then
  ok "Audience-mapper voor Trino staat er al"
else
  kc create "clients/$TRID/protocol-mappers/models" -r $R \
    -s name=audience-trino -s protocol=openid-connect -s protocolMapper=oidc-audience-mapper \
    -s 'config."included.client.audience"=df-trino' -s 'config."access.token.claim"=true' \
    -s 'config."id.token.claim"=false' >/dev/null
  ok "Audience-mapper voor Trino toegevoegd"
fi

# --- AMR-mapper ----------------------------------------------------------------------
if kc get "clients/$ID/protocol-mappers/models" -r $R | jq -e '.[] | select(.protocolMapper == "oidc-amr-mapper")' >/dev/null; then
  ok "AMR-mapper staat er al"
else
  kc create "clients/$ID/protocol-mappers/models" -r $R \
    -s name=amr -s protocol=openid-connect -s protocolMapper=oidc-amr-mapper \
    -s 'config."id.token.claim"=true' -s 'config."access.token.claim"=true' \
    -s 'config."introspection.token.claim"=true' >/dev/null
  ok "AMR-mapper toegevoegd"
fi

# --- Referentiewaarde op de OTP-stap ---------------------------------------------------
FLOW="$(kc get "realms/$R" --fields browserFlow | jq -r '.browserFlow // "browser"')"
EXEC="$(kc get "authentication/flows/$(jq -rn --arg f "$FLOW" '$f|@uri')/executions" -r $R | jq -c '[.[] | select(.providerId == "auth-otp-form")][0] // empty')"
if [ -z "$EXEC" ]; then
  waarschuw "De inlogflow '$FLOW' heeft geen OTP-stap. Zonder tweede factor laat het portaal niemand binnen."
elif [ "$(echo "$EXEC" | jq -r '.authenticationConfig // empty')" ]; then
  ok "De OTP-stap heeft al een configuratie"
else
  EID="$(echo "$EXEC" | jq -r .id)"
  if kc create "authentication/executions/$EID/config" -r $R \
       -s alias=df-otp-referentie -s 'config."default.reference.value"=otp' >/dev/null 2>&1; then
    ok "OTP-stap meldt nu 'otp' in amr"
  else
    waarschuw "Zet in Keycloak bij Authentication → $FLOW → OTP Form → instellingen 'Authentication Reference' op otp."
  fi
fi

# --- Een gebruiker voor jezelf -----------------------------------------------------------
echo
echo "  Je logt op het portaal in met een Keycloak-gebruiker met een geverifieerd"
echo "  e-mailadres. Zal ik er een voor je maken?"
read -r -p "  Jouw e-mailadres (leeg = overslaan): " EMAIL
EMAIL="${EMAIL,,}"
if [ -n "$EMAIL" ]; then
  [[ "$EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[a-z]{2,}$ ]] || stop "Dat is geen e-mailadres."
  UID_="$(kc get users -r $R -q email="$EMAIL" -q exact=true --fields id | jq -r '.[0].id // empty')"
  if [ -n "$UID_" ]; then
    kc update "users/$UID_" -r $R -s emailVerified=true >/dev/null
    ok "$EMAIL bestaat al; e-mail als geverifieerd gemarkeerd"
  else
    read -r -p "  Voornaam: " VOOR
    read -r -p "  Achternaam: " ACHTER
    TIJDELIJK="Tijdelijk-$(geheim 6)"
    kc create users -r $R -s username="$EMAIL" -s email="$EMAIL" -s emailVerified=true -s enabled=true \
      -s firstName="$VOOR" -s lastName="$ACHTER" \
      -s 'requiredActions=["UPDATE_PASSWORD","CONFIGURE_TOTP"]' >/dev/null
    kc set-password -r $R --username "$EMAIL" --new-password "$TIJDELIJK" --temporary >/dev/null
    ok "Gebruiker $EMAIL aangemaakt"
    echo "      Tijdelijk wachtwoord: $TIJDELIJK"
    echo "      Bij de eerste inlog kies je een eigen wachtwoord en koppel je een authenticator-app."
  fi
  echo "      Maak in het portaal (via /emergency) een account met precies dit e-mailadres."
  # De eerste beheerder van OpenMetadata: OpenMetadata kent je als het deel vóór de @.
  if [ -z "$(waarde OM_BEHEERDER)" ]; then
    zet OM_BEHEERDER "${EMAIL%@*}"
    zet OM_DOMEIN "${EMAIL#*@}"
    ok "Beheerder van OpenMetadata: ${EMAIL%@*}"
  fi
fi

# --- Het portaal koppelen ------------------------------------------------------------------
SECRET="$(kc get "clients/$ID/client-secret" -r $R | jq -r .value)"
OMSECRET="$(kc get "clients/$OMID/client-secret" -r $R | jq -r .value)"
TRSECRET="$(kc get "clients/$TRID/client-secret" -r $R | jq -r .value)"
docker compose exec -T keycloak rm -f /tmp/df-kcadm.config
zet PORTAAL_OIDC_ISSUER "https://id.$DOMEIN/realms/$R"
zet PORTAAL_OIDC_GEHEIM "$SECRET"
zet OM_OIDC_GEHEIM "$OMSECRET"
zet TRINO_OIDC_GEHEIM "$TRSECRET"
docker compose up -d portaal-migreer portaal openmetadata trino >/dev/null
ok "Het portaal, OpenMetadata en Trino loggen nu in via Keycloak (geheimen en uitgever staan in compose/.env)"
