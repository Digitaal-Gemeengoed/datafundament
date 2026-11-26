-- Dataproduct: testpersonen per buurt, naast de kerncijfers van CBS.
-- Combineert administratieve gegevens (BRP-testdata) met geodata (BAG, CBS).
-- Staat in het lakehouse (Iceberg) en, met echte geometrie, in PostGIS
-- (dataproduct dwh_testpersonen_per_buurt).
with levend as (
    select p.pl_id, p.leeftijd_ongeveer, a.buurtcode
    from {{ ref('persoon') }} as p
    join {{ ref('adres') }} as a using (pl_id)
    where not p.overleden and a.buurtcode is not null
)
select
    b.buurtcode,
    b.buurtnaam,
    b.wijkcode,
    b.gemeentecode,
    b.gemeentenaam,
    count(l.pl_id)                                                     as testpersonen,
    count(l.pl_id) filter (where l.leeftijd_ongeveer < 18)            as testpersonen_0_17,
    count(l.pl_id) filter (where l.leeftijd_ongeveer between 18 and 64) as testpersonen_18_64,
    count(l.pl_id) filter (where l.leeftijd_ongeveer >= 65)           as testpersonen_65_plus,
    b.aantal_inwoners_cbs,
    round(1000.0 * count(l.pl_id) / nullif(b.aantal_inwoners_cbs, 0), 2) as testpersonen_per_1000_inwoners,
    b.geometrie_wkb,
    current_timestamp                                                  as gemaakt_op
from {{ ref('buurt') }} as b
left join levend as l using (buurtcode)
group by all
