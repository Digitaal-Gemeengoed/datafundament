{{
  config(
    database='dwh',
    schema='dataproduct',
    alias='testpersonen_per_buurt',
    materialized='table',
    post_hook=[
      "CALL postgres_execute('dwh', 'ALTER TABLE dataproduct.testpersonen_per_buurt ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 28992)')",
      "CALL postgres_execute('dwh', 'UPDATE dataproduct.testpersonen_per_buurt SET geom = ST_SetSRID(ST_GeomFromWKB(geometrie_wkb), 28992)')",
      "CALL postgres_execute('dwh', 'ALTER TABLE dataproduct.testpersonen_per_buurt ADD PRIMARY KEY (buurtcode)')",
      "CALL postgres_execute('dwh', 'CREATE INDEX IF NOT EXISTS testpersonen_per_buurt_geom ON dataproduct.testpersonen_per_buurt USING gist (geom)')",
      "CALL postgres_execute('dwh', 'ALTER TABLE dataproduct.testpersonen_per_buurt ADD COLUMN IF NOT EXISTS geom_wkt text')",
      "CALL postgres_execute('dwh', 'UPDATE dataproduct.testpersonen_per_buurt SET geom_wkt = ST_AsText(geom)')"
    ]
  )
}}
-- Hetzelfde dataproduct in PostGIS (DF-ADR-001): met een echte geometriekolom,
-- een sleutel en een ruimtelijke index, voor QGIS en ruimtelijke vragen.
-- geom_wkt is er voor Trino, dat geometrie uit PostgreSQL niet kent (DF-ADR-008).
select * from {{ ref('testpersonen_per_buurt') }}
