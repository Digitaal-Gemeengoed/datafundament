"""Dagster: de keten van het Datafundament als assets.

  bron_<bron>/*       de tabellen van een bron op dfw (extern): brp, bag, woz,
                      belastingen, mor, zaken, sociaal
  ruw_<bron>/*        ingestie met dlt, insert-only (elke versie)
  ruw_<bron>_stand/*  ingestie met dlt, de huidige stand
  ruw_pdok/*        adressen opgezocht in de BAG (Locatieserver), buurten van CBS
  uniform/*         dbt: de uniforme laag (Iceberg)
  dataproduct/*     dbt: dataproducten (Iceberg en PostGIS)

Elke asset is een tabel; de lineage loopt van bron tot dataproduct.
"""

from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    DefaultScheduleStatus,
    Definitions,
    MaterializeResult,
    OpExecutionContext,
    DagsterRunStatus,
    RunRequest,
    RunsFilter,
    ScheduleEvaluationContext,
    SkipReason,
    schedule,
    asset,
    define_asset_job,
    job,
    multi_asset,
    op,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from beheer import onderhoud
from orkestratie import metadata as om
from orkestratie.verwijderen import verwijderen
from ingestie import bronnen, pdok


# --- Ingestie van de bronnen ---------------------------------------------------

SOORT = {"database": ("postgres", "{b}.{t} in de bron-database op dfw"),
         "api": ("api", "{t} uit de Zaken-API op dfw"),
         "bestand": ("csv", "{t} uit de nachtelijke export in de landingsbucket")}


def bron_specs():
    specs = []
    for b, info in bronnen.BRONNEN.items():
        soort, tekst = SOORT[info.get("soort", "database")]
        specs += [AssetSpec([f"bron_{b}", t], group_name="bron", kinds={soort},
                            description=tekst.format(b=b, t=t) + f" ({info['omschrijving']})")
                  for t in bronnen.alle_tabellen(b)]
    return specs


def ingestie(bron, laag, omschrijving):
    specs = [
        AssetSpec([laag, t], group_name=laag, kinds={"dlt", "iceberg"}, deps=[[f"bron_{bron}", t]],
                  description=f"{t}: {omschrijving}")
        for t in bronnen.alle_tabellen(bron)
    ]

    @multi_asset(name=f"laad_{laag}", specs=specs, can_subset=False)
    def _laad(context: AssetExecutionContext):
        rijen, verslag = bronnen.laad(bron, laag)
        context.log.info(f"{laag}: {sum(rijen.values())} rijen geladen; CDC: {verslag}")
        if verslag.get("toast"):
            context.log.warning(f"{verslag['toast']} ongewijzigde TOAST-waarden niet meegekomen (zie ingestie/cdc.py)")
        for t in bronnen.alle_tabellen(bron):
            yield MaterializeResult(asset_key=[laag, t], metadata={"rijen_geladen": rijen.get(t, 0), "cdc": verslag["slot"],
                                                                   **({"verwijderd": verslag["verwijderd"]} if "verwijderd" in verslag else {})})

    return _laad


LADERS = [
    ingestie(b, laag, "elke versie van elke rij (insert-only)" if laag == f"ruw_{b}"
             else "de huidige stand (upsert op id)")
    for b in bronnen.BRONNEN for laag in bronnen.lagen(b)
]


# --- Geodata van PDOK ----------------------------------------------------------

@asset(key=["ruw_pdok", "adres_locatie"], group_name="ruw_pdok", kinds={"dlt", "iceberg"},
       deps=[["ruw_brp_stand", "verblijfplaats"]],
       description="Actuele adressen opgezocht in de BAG (PDOK Locatieserver): RD-punt en buurtcode. "
                   "Alleen nieuwe adressen.")
def adres_locatie(context: AssetExecutionContext):
    n = pdok.laad(pdok.adres_locatie)
    context.log.info(f"{n} nieuwe adressen opgezocht")
    return MaterializeResult(metadata={"nieuw_opgezocht": n})


@asset(key=["ruw_pdok", "cbs_buurten"], group_name="ruw_pdok", kinds={"dlt", "iceberg"},
       deps=[["ruw_pdok", "adres_locatie"]],
       description="CBS Wijken en Buurten 2025 (CC-BY 4.0): buurten met kerncijfers, "
                   "voor de gemeenten waar de testpersonen wonen.")
def cbs_buurten(context: AssetExecutionContext):
    n = pdok.laad(pdok.cbs_buurten)
    return MaterializeResult(metadata={"buurten": n})


# --- dbt: uniforme laag en dataproducten -----------------------------------------

DBT = DbtProject(project_dir=Path(__file__).resolve().parent.parent / "transformatie")


class Vertaler(DagsterDbtTranslator):
    """Bronnen heten zoals de assets van de ingestie; modellen krijgen hun schema
    als voorvoegsel (uniform/persoon, dataproduct/..., dwh/dataproduct/...)."""

    def get_asset_key(self, dbt_resource_props):
        if dbt_resource_props["resource_type"] == "source":
            return AssetKey([dbt_resource_props["source_name"], dbt_resource_props["name"]])
        config = dbt_resource_props.get("config", {})
        schema = config.get("schema") or dbt_resource_props.get("schema")
        naam = dbt_resource_props.get("alias") or dbt_resource_props["name"]
        if config.get("database") == "dwh":
            return AssetKey(["dwh", schema, naam])
        return AssetKey([schema, naam])

    def get_group_name(self, dbt_resource_props):
        return dbt_resource_props.get("config", {}).get("schema") or "dbt"


@dbt_assets(manifest=DBT.manifest_path, project=DBT, dagster_dbt_translator=Vertaler())
def dbt_modellen(context: AssetExecutionContext, dbt: DbtCliResource):
    build = dbt.cli(["build"], context=context)
    try:
        yield from build.stream()
    finally:
        # Ook na een mislukte test: de uitkomst gaat naar OpenMetadata (DF-ADR-007).
        om.bewaar_dbt_uitkomst(build.target_path)


# --- Onderhoud ------------------------------------------------------------------------

@op
def snapshots_opruimen(context: OpExecutionContext):
    """Snapshots ouder dan een week opruimen, in alle Iceberg-tabellen."""
    opgeruimd = onderhoud.snapshots_opruimen(7, log=context.log.info)
    return sum(opgeruimd.values())


@job(description="Onderhoud van het lakehouse (DF-ADR-014)")
def onderhoud_lakehouse():
    snapshots_opruimen()


# --- Jobs en schema's --------------------------------------------------------------

ingestie_job = define_asset_job("ingestie", selection=AssetSelection.assets(*LADERS))

BEZIG = [DagsterRunStatus.QUEUED, DagsterRunStatus.NOT_STARTED, DagsterRunStatus.STARTING, DagsterRunStatus.STARTED]


def periodiek(naam, job_def, cron):
    """Een schema dat overslaat zolang er van deze job nog een run wacht of loopt.
    Zo groeit de wachtrij niet als een run lang duurt of vastzit."""
    @schedule(name=naam, job=job_def, cron_schedule=cron, execution_timezone="Europe/Amsterdam",
              default_status=DefaultScheduleStatus.RUNNING)
    def _schema(context: ScheduleEvaluationContext):
        bezig = context.instance.get_runs_count(RunsFilter(job_name=job_def.name, statuses=BEZIG))
        if bezig:
            return SkipReason(f"Er wacht of loopt al een run van {job_def.name}")
        return RunRequest()
    return _schema
keten_job = define_asset_job("keten", selection=AssetSelection.all() - AssetSelection.groups("bron"))

defs = Definitions(
    assets=bron_specs() + LADERS + [adres_locatie, cbs_buurten, dbt_modellen],
    jobs=[ingestie_job, keten_job, onderhoud_lakehouse, verwijderen, om.metadata],
    sensors=[om.sensor(keten_job)],
    resources={"dbt": DbtCliResource(project_dir=DBT)},
    schedules=[
        # Snel: wijzigingen in de bronnen komen binnen enkele minuten in de ruwe laag.
        periodiek("ingestie_elke_5_minuten", ingestie_job, "*/5 * * * *"),
        # 's Nachts: oude snapshots opruimen.
        periodiek("onderhoud_elke_nacht", onderhoud_lakehouse, "37 3 * * *"),
        # De hele keten, tot en met de dataproducten.
        periodiek("keten_elk_kwartier", keten_job, "2,17,32,47 * * * *"),
    ],
)
