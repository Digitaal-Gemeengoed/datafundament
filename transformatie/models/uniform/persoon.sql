-- Uniforme laag: de actuele stand van elke persoon, met leesbare waarden.
-- Datums als DATE, codes met omschrijving (codetabel van de bron).
with persoon as (
    select * from {{ source('ruw_brp_stand', 'persoon') }} where actueel
),
codes as (
    select element, code, omschrijving from {{ source('ruw_brp_stand', 'codetabel') }}
),
overleden as (
    select pl_id, min({{ brp_datum('datum_overlijden') }}) as datum_overlijden
    from {{ source('ruw_brp_stand', 'overlijden') }}
    where actueel
    group by pl_id
)
select
    pl.id                                           as pl_id,
    -- Geen BSN, A-nummer of naam: die komen niet in het lakehouse (DF-ADR-015).
    pl.pseudoniem,
    {{ brp_datum('p.geboortedatum') }}              as geboortedatum,
    p.geslachtsaanduiding                           as geslacht_code,
    g.omschrijving                                  as geslacht,
    o.datum_overlijden,
    o.pl_id is not null                             as overleden,
    case when o.pl_id is null and {{ brp_datum('p.geboortedatum') }} is not null
         then date_diff('year', {{ brp_datum('p.geboortedatum') }}, current_date)
    end                                             as leeftijd_ongeveer,
    pl.testsets
from {{ source('ruw_brp_stand', 'persoonslijst') }} as pl
join persoon as p on p.pl_id = pl.id
left join codes as g on g.element = '04.10' and g.code = p.geslachtsaanduiding
left join overleden as o on o.pl_id = pl.id
