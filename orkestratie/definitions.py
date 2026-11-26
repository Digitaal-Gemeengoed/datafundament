"""Dagster: de keten van het Datafundament als assets.

Nu: de ingestie van de bron naar de ruwe laag, per tabel een asset, zodat de
lineage per tabel zichtbaar is. dbt (uniforme laag en dataproducten) komt hier
bovenop.
"""

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    AssetSpec,
    DefaultScheduleStatus,
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    define_asset_job,
    multi_asset,
)

from ingestie import brp

BRON = "bron_brp"  # de tabellen op dfw, als externe assets


def bron_specs():
    return [
        AssetSpec([BRON, t], group_name="bron", kinds={"postgres"},
                  description=f"brp.{t} in de bron op dfw (testdata vrijBRP)")
        for t in brp.ALLE_TABELLEN
    ]


def ingestie(laag, omschrijving):
    specs = [
        AssetSpec([laag, t], group_name=laag, kinds={"dlt", "iceberg"}, deps=[[BRON, t]],
                  description=f"{t}: {omschrijving}")
        for t in brp.ALLE_TABELLEN
    ]

    @multi_asset(name=f"laad_{laag}", specs=specs, can_subset=False)
    def _laad(context: AssetExecutionContext):
        rijen = brp.laad(laag)
        context.log.info(f"{laag}: {sum(rijen.values())} rijen geladen")
        for t in brp.ALLE_TABELLEN:
            yield MaterializeResult(asset_key=[laag, t], metadata={"rijen_geladen": rijen[t]})

    return _laad


laad_ruw = ingestie("ruw_brp", "elke versie van elke rij (insert-only)")
laad_stand = ingestie("ruw_brp_stand", "de huidige stand (upsert op id)")

ingestie_job = define_asset_job("ingestie_brp", selection=AssetSelection.assets(laad_ruw, laad_stand))

defs = Definitions(
    assets=bron_specs() + [laad_ruw, laad_stand],
    jobs=[ingestie_job],
    schedules=[
        ScheduleDefinition(
            name="ingestie_elke_5_minuten",
            job=ingestie_job,
            cron_schedule="*/5 * * * *",
            execution_timezone="Europe/Amsterdam",
            default_status=DefaultScheduleStatus.RUNNING,
        )
    ],
)
