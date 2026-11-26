-- Uniforme laag: buurten van CBS (Wijken en Buurten 2025, CC-BY 4.0) met
-- kerncijfers en geometrie in RD (EPSG:28992), als WKB. Waarden onder nul zijn
-- bij CBS geheimgehouden of onbekend; die worden NULL.
with b as (
    select
        *,
        ST_GeomFromGeoJSON(geometrie_geojson) as geom_bron
    from {{ source('ruw_pdok', 'cbs_buurten') }}
)
select
    buurtcode,
    buurtnaam,
    wijkcode,
    gemeentecode,
    gemeentenaam,
    case when aantal_inwoners >= 0 then aantal_inwoners end         as aantal_inwoners_cbs,
    case when aantal_huishoudens >= 0 then aantal_huishoudens end   as aantal_huishoudens_cbs,
    jaar                                                            as jaar_cbs,
    ST_AsWKB(
        case when crs like '%28992%' then geom_bron
             else ST_Transform(geom_bron, 'EPSG:4326', 'EPSG:28992', always_xy := true)
        end
    )                                                               as geometrie_wkb
from b
