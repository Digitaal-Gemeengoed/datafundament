# Inlogthema `datafundament`

Het inlogscherm en de e-mails van Keycloak in de stijl van het portaal: het merkblok DF, dezelfde Utrecht-componenten, het Haarlem-thema van NL Design System en dezelfde eigen tokens. Gebaseerd op het thema `oa` van de Office Assistent (oa-uitrol/keycloak-thema), met dezelfde opbouw en uitleg bij herstel en herstelcodes.

- `login/theme.properties`: bouwt voort op het basisthema van Keycloak. Alleen de opmaak (`template.ftl`) en de pagina voor de code uit de app (`login-otp.ftl`) zijn eigen.
- `login/resources/css/`:
  - `haarlem-theme.css`: het Haarlem-thema (`@nl-design-system-unstable/haarlem-design-tokens` 1.0.0, net als in het portaal);
  - `utrecht.css`: alleen de Utrecht-componenten die het thema gebruikt (uit oa-uitrol);
  - `df-tokens.css`: de tokens van het portaal (`portaal/frontend/src/stijl.css`). Veranderen die daar, neem het blok dan opnieuw over;
  - `df-login.css`: de eigen opmaak.
- `login/messages/` en `email/messages/`: eigen teksten in het Nederlands en Engels. De rest komt uit Keycloak.

**Huisstijl.** Het Haarlem-thema mag alleen de gemeente Haarlem gebruiken (zie de licentie van het pakket). Het lettertype Sofia Pro laden we niet; dat vraagt een licentie. Wie dit elders gebruikt, vervangt `haarlem-theme.css` door het voorbeeldthema van NL Design System (zoals in oa-uitrol) of door een eigen thema.

**Op de server.** `compose/compose.yml` koppelt deze map aan in Keycloak, `server/keycloak.sh` zet het thema op het realm, en `installeer-platform.sh` herstart Keycloak, want Keycloak houdt thema's in het geheugen.

**Lokaal proberen.** Gebruik een uitgepakte Keycloak 26.8.2:

```sh
ln -s "$PWD/datafundament" keycloak-26.8.2/themes/datafundament
keycloak-26.8.2/bin/kc.sh start-dev --spi-theme--cache-themes=false --spi-theme--cache-templates=false
```

Kies daarna het thema `datafundament` bij het realm.
