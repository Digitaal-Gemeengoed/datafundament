-- Dataproduct: testpersonen per buurt, naast de kerncijfers van CBS.
-- Combineert administratieve gegevens (BRP-testdata) met geodata (BAG, CBS).
-- Staat in het lakehouse (Iceberg) en, met echte geometrie, in PostGIS
-- (dataproduct dwh_testpersonen_per_buurt).
with levend as (
    -- Levende testpersonen met een adres dat in een buurt ligt.
    select p.pl_id, p.leeftijd_ongeveer, a.buurtcode
    from {{ ref('persoon') }} as p
    join {{ ref('adres') }} as a using (pl_id)
    where not p.overleden and a.buurtcode is not null
),
per_buurt as (
    -- Eerst tellen per buurt ...
    select
        buurtcode,
        count(*)                                              as testpersonen,
        count(*) filter (where leeftijd_ongeveer < 18)           as testpersonen_0_17,
        count(*) filter (where leeftijd_ongeveer between 18 and 64) as testpersonen_18_64,
        count(*) filter (where leeftijd_ongeveer >= 65)          as testpersonen_65_plus
    from levend
    group by buurtcode
)
-- ... dan koppelen aan alle buurten; een buurt zonder testpersonen telt 0.
select
    b.buurtcode,
    b.buurtnaam,
    b.wijkcode,
    b.gemeentecode,
    b.gemeentenaam,
    coalesce(t.testpersonen, 0)                                as testpersonen,
    coalesce(t.testpersonen_0_17, 0)                           as testpersonen_0_17,
    coalesce(t.testpersonen_18_64, 0)                          as testpersonen_18_64,
    coalesce(t.testpersonen_65_plus, 0)                        as testpersonen_65_plus,
    b.aantal_inwoners_cbs,
    round(1000.0 * coalesce(t.testpersonen, 0) / nullif(b.aantal_inwoners_cbs, 0), 2)
                                                               as testpersonen_per_1000_inwoners,
    b.geometrie_wkb,
    current_timestamp                                          as gemaakt_op
from {{ ref('buurt') }} as b
left join per_buurt as t using (buurtcode)
