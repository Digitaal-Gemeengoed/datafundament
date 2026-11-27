-- df-portaal, migratie 006: het recht platform.bedienen (DF-ADR-018).
-- Wie het heeft, komt via de poort (oauth2-proxy met Keycloak) bij Dagster en de
-- Iceberg-catalogus. Dagster kent geen rollen: daar kan wie binnen is alles.
SET search_path = beheer, public;

ALTER TABLE groepen DROP CONSTRAINT IF EXISTS groepen_rechten_check;
ALTER TABLE groepen ADD CONSTRAINT groepen_rechten_check CHECK (rechten <@ ARRAY[
  'accounts.view', 'accounts.manage', 'groups.view', 'groups.manage', 'audit.view', 'settings.view', 'settings.manage',
  'platform.view', 'dataproducten.view', 'toegang.aanvragen', 'toegang.beoordelen',
  'verwijderen.aanvragen', 'verwijderen.beoordelen', 'datavragen.view', 'lagen.lezen', 'platform.bedienen'
]::text[]);
