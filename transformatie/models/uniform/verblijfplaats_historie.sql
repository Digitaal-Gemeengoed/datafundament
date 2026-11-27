-- Uniforme laag: de tijdlijn (SCD2) van elke verblijfplaats, gemaakt uit de
-- insert-only ruwe laag (DF-ADR-005). Elke versie van een record krijgt
-- geldig_vanaf (wanneer de bron hem zo liet zien) en geldig_tot (de volgende versie).
-- Daarnaast de datums uit de BRP zelf (aanvang adreshouding, ingang geldigheid).
-- Een verwijdering in de bron (via CDC, DF-ADR-006) sluit de tijdlijn af op het
-- moment van de commit; de verwijdering zelf is geen versie.
with versies as (
    select
        *,
        coalesce(gewijzigd_op, _cdc_tijdstip) as moment,
        coalesce(_cdc_bewerking = 'D', false) as verwijderd,
        row_number() over (partition by id, gewijzigd_op, coalesce(_cdc_bewerking = 'D', false)
                           order by _dlt_load_id desc, _cdc_lsn desc nulls last) as nr
    from {{ source('ruw_brp', 'verblijfplaats') }}
),
tijdlijn as (
    select
        *,
        lead(moment) over (partition by id order by moment, verwijderd) as volgende
    from versies
    where nr = 1
),
uniek as (
    select * from tijdlijn where not verwijderd
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
    v.moment                                          as geldig_vanaf,
    v.volgende                                        as geldig_tot,
    v.volgende is null                                as huidige_versie,
    v._dlt_load_id                                    as geladen_in
from uniek as v
left join gemeenten as g on g.code = v.gemeente_van_inschrijving
