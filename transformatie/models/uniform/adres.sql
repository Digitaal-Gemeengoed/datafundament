-- Uniforme laag: het actuele Nederlandse adres van elke persoon, met de locatie
-- uit de BAG (Locatieserver) als punt in RD (EPSG:28992), als WKB (DF-ADR-004).
with actueel as (
    select * from {{ source('ruw_brp_stand', 'verblijfplaats') }}
    where actueel and coalesce(postcode, '') <> '' and coalesce(huisnummer, '') <> ''
)
select
    a.pl_id,
    a.straatnaam,
    a.huisnummer,
    nullif(a.huisletter, '')                         as huisletter,
    a.postcode,
    nullif(a.woonplaatsnaam, '')                     as woonplaatsnaam,
    l.gevonden                                       as gevonden_in_bag,
    l.weergavenaam                                   as bag_weergavenaam,
    l.nummeraanduiding_id,
    l.buurtcode,
    l.buurtnaam,
    l.wijkcode,
    l.gemeentecode,
    l.gemeentenaam,
    case when l.centroide_rd is not null
         then ST_AsWKB(ST_GeomFromText(l.centroide_rd)) end  as locatie_wkb
from actueel as a
left join {{ source('ruw_pdok', 'adres_locatie') }} as l
    on l.sleutel = a.postcode || '|' || a.huisnummer || '|' || coalesce(a.huisletter, '')
