"""Een aanvulling op pyiceberg 0.12: upsert na een nieuwe kolom.

Bij een upsert leest pyiceberg de bestaande rijen met het schema van de laatste
snapshot. Heeft dlt net een kolom toegevoegd (een nieuwe kolom in de bron, of de
kolommen van CDC), dan missen die rijen die kolom en faalt de vergelijking
("Target schema's field names are not matching"). Hier vullen we de ontbrekende
kolommen aan als leeg; dat is ook wat ze in Iceberg zijn. Een rij met een waarde
in de nieuwe kolom telt dan als gewijzigd, en wordt bijgewerkt.

Weg te halen zodra pyiceberg dit zelf doet.
"""

import pyarrow as pa
from pyiceberg.table import upsert_util

_origineel = upsert_util.get_rows_to_update


def _aangevuld(source_table, target_table, join_cols):
    for veld in source_table.schema:
        if veld.name not in target_table.column_names:
            target_table = target_table.append_column(veld, pa.nulls(len(target_table), veld.type))
    target_table = target_table.select(source_table.column_names)
    return _origineel(source_table, target_table, join_cols)


if not getattr(upsert_util.get_rows_to_update, "_datafundament", False):
    _aangevuld._datafundament = True
    upsert_util.get_rows_to_update = _aangevuld
