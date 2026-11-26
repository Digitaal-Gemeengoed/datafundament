-- Uniforme laag: de tijdlijn (SCD2) van elke verblijfplaats, gemaakt uit de
-- insert-only ruwe laag (DF-ADR-005). Elke versie van een record krijgt
-- geldig_vanaf (wanneer de bron hem zo liet zien) en geldig_tot (de volgende versie).
-- Daarnaast de datums uit de BRP zelf (aanvang adreshouding, ingang geldigheid).
with versies as (
    select
        *,
        row_number() over (partition by id, gewijzigd_op order by _dlt_load_id desc) as nr
    from {{ source('ruw_brp', 'verblijfplaats') }}
),
uniek as (
    select * from versies where nr = 1
),
gemeenten as (
    select code, omschrijving from {{ source('ruw_brp_stand', 'codetabel') }} where element = '09.10'
)
select
    v.id                                              as record_id,
    v.pl_id,
    v.stapel,
    v.volgnr,
    v.actueel                                         as actueel_in_bron,
    v.onjuist,
    nullif(v.straatnaam, '')                          as straatnaam,
    nullif(v.huisnummer, '')                          as huisnummer,
    nullif(v.huisletter, '')                          as huisletter,
    nullif(v.huisnummertoevoeging, '')                as huisnummertoevoeging,
    nullif(v.postcode, '')                            as postcode,
    nullif(v.woonplaatsnaam, '')                      as woonplaatsnaam,
    v.gemeente_van_inschrijving                       as gemeente_code,
    g.omschrijving                                    as gemeente,
    nullif(v.land_waarnaar_vertrokken, '')            as land_vertrokken_code,
    {{ brp_datum('v.datum_aanvang_adreshouding') }}   as datum_aanvang_adreshouding,
    {{ brp_datum('v.ingangsdatum_geldigheid') }}      as ingangsdatum_geldigheid,
    v.gewijzigd_op                                    as geldig_vanaf,
    lead(v.gewijzigd_op) over (partition by v.id order by v.gewijzigd_op) as geldig_tot,
    lead(v.gewijzigd_op) over (partition by v.id order by v.gewijzigd_op) is null as huidige_versie,
    v._dlt_load_id                                    as geladen_in
from uniek as v
left join gemeenten as g on g.code = v.gemeente_van_inschrijving
