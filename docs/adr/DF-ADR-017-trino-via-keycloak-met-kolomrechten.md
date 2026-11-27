# DF-ADR-017 — Trino via Keycloak, met rechten per kolom uit het portaal

- **Status:** aanvaard
- **Datum:** 27 november 2026
- **Besloten door:** Erik Hoekstra, op voorstel van Claude

## Context

Trino is de enige voordeur (DF-ADR-008). Tot nu toe stond er één wachtwoord van Caddy voor. Trino kende daardoor geen personen, en het log van de datavragen (DF-ADR-016) toonde de naam die de client zelf opgaf. Het portaal kent wel toekenningen per dataproduct, met doel en grondslag (DF-ADR-013), maar die waren nog een voorstel om in Git te zetten.

## Besluit

**Inloggen**

- **Trino logt in via Keycloak** (OAuth2, client `df-trino`), in de web-UI en vanuit JDBC of de CLI met `externalAuthentication=true`. De gebruiker is het e-mailadres. Keycloak vraagt de tweede factor.
- **Diensten** loggen in met een wachtwoord uit een bcrypt-bestand. Nu is dat alleen `openmetadata`. Trino neemt een wachtwoord alleen over TLS aan, dus OpenMetadata komt via Caddy binnen.
- **Caddy** zet geen eigen wachtwoord meer voor Trino.

**Rechten**

- **Wie wat mag**, staat in een JSON-bestand met regels (file-based access control). Het portaal schrijft dat bestand (`trinoregels.ts`) als er iets veranderde, en kijkt elke 30 seconden. Trino leest het elke minuut. De regels:
  - **Data-engineers** (het recht `lagen.lezen`) en de dienst `openmetadata` lezen alle lagen.
  - **Een toekenning** geeft leesrecht op dat ene dataproduct. Kolommen met het label `persoonsgegeven` of `bijzonder` (`meta.privacy` in dbt) zijn gemaskeerd: ze zijn leeg. Dat geldt niet als de beoordelaar bij het besluit **'met persoonsgegevens'** aanvinkte. Dat vinkje ligt daarna vast; de database weigert het te wijzigen.
  - **Verlopen** toekenningen tellen niet mee, en ook niet die van geblokkeerde accounts.
  - **Verder** mag niemand iets.
- **Het manifest van dbt** zegt welke kolommen gevoelig zijn. Het portaal leest het uit de laatste `dbt build`. Ontbreekt het manifest, dan is niet bekend wat gevoelig is. Dan gaat alleen een toekenning met persoonsgegevens open: bij twijfel dicht.
- **`lagen.lezen` komt niet mee met superadmin.** Beheer van het portaal is geen toegang tot data.

## Gevolgen

- In het log van de datavragen staat nu een geverifieerde persoon (DF-ADR-016).
- Een toekenning in het portaal werkt binnen ongeveer twee minuten in Trino. Een intrekking ook.
- De labels staan bij het model, in Git. Wie een kolom met persoonsgegevens aan een dataproduct toevoegt, moet hem daar labelen. Een review van het dbt-model hoort dat te zien. In `uniform.persoon` staan de labels als voorbeeld.
- De huidige dataproducten zijn tellingen per buurt, zonder gelabelde kolommen. Het maskeren gaat dus pas spelen bij het eerste dataproduct met persoonsgegevens.
- **Afnemers** verbinden voortaan met `jdbc:trino://trino.<domein>:443?SSL=true&externalAuthentication=true`. Bij het verbinden opent de browser voor Keycloak. Het oude wachtwoord van Caddy werkt voor Trino niet meer.

## Overwogen

- **Per aanvraag kolommen kiezen:** fijnmaziger, maar meer werk bij elke aanvraag. Het risico dat iemand iets aanvinkt zonder het te overzien, is groter.
- **Rechten via groepen in Keycloak:** dan staat de toegang los van doel en grondslag. Precies die horen bij een toekenning.
- **Ranger of OPA:** krachtiger, maar elk is een extra onderdeel om te beheren. Het bestand van Trino volstaat voor een PoC, en wat erin staat, is te volgen.
