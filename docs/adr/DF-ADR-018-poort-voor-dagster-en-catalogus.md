# DF-ADR-018 — Een poort via Keycloak voor Dagster en de catalogus

- **Status:** aanvaard
- **Datum:** 27 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

Het portaal, Trino en OpenMetadata loggen in via Keycloak (DF-ADR-012, DF-ADR-017). Dagster en de web-UI van Lakekeeper hebben in hun open-source versies geen inlog die met Keycloak samenwerkt. Er stond één gedeeld wachtwoord van Caddy voor, en daarmee was niet te zien wie er binnen was. Dagster kent ook geen rollen: wie binnen is, kan runs starten, ook de job `verwijderen`.

## Besluit

- **oauth2-proxy als poort.** Caddy vraagt bij elke aanvraag aan `dagster.` en `catalogus.` aan oauth2-proxy (`forward_auth`) of de bezoeker binnen mag. Niet ingelogd: door naar Keycloak, met dezelfde inlog en tweede factor als het portaal. Ingelogd maar zonder recht: 403.
- **Wie binnen mag, bepaalt het portaal.** Het gaat om actieve accounts met het nieuwe recht **platform.bedienen** ("Dagster en catalogus bedienen"), of met superadmin. Het portaal schrijft hun e-mailadressen naar een bestand. oauth2-proxy leest dat opnieuw zodra het verandert. Het hoofdaccount (noodaccount) staat er nooit op: dat logt niet in via Keycloak.
- **Eén cookie** voor alle namen onder het domein (`__Secure-df_poort`, 12 uur geldig). Wie bij Dagster is ingelogd, is dat ook bij de catalogus.
- **Het gedeelde wachtwoord verdwijnt.** De startpagina bevat alleen links en staat open (`noindex`).
- **Herstelcodes** zoals bij de Office Assistent. Na het koppelen van de app maakt iedereen twaalf codes, en een code kan bij het inloggen in plaats van de app. Het portaal ziet dat als tweede factor (`amr` "mfa").

## Gevolgen

- Overal één inlog. Toegang tot Dagster is een recht in het portaal, met audit op het toekennen.
- **In Dagster is wie binnen is, gelijk.** Een run zie je in Dagster zelf, maar niet wie hem startte. Het recht hoort dus bij een kleine groep platformbeheerders.
- **Het portaal leest Dagster intern** (GraphQL op het compose-netwerk), niet via de poort. Daar verandert niets.
- **Superadmin geeft dit recht wel**, anders dan `lagen.lezen` (DF-ADR-017). Dagster en de catalogus tonen metadata en runs, geen inhoud van tabellen.

## Overwogen

- **Dagster+** (de betaalde variant, met SSO en rollen): niet open source.
- **Een groep in Keycloak in plaats van een recht in het portaal:** dan staan de rechten op twee plekken.
- **Basic auth per persoon in Caddy:** wachtwoorden zonder tweede factor, en buiten Keycloak.
