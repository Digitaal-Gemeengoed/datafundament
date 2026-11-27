"""OpenMetadata bijwerken, als job in Dagster, zonder Airflow (DF-ADR-007).

Na een geslaagde run van de keten, hoogstens één keer per uur:

  1. dbt docs generate: manifest en catalogus, in /var/lib/dbt/docs;
  2. de catalogus uit Trino (metadata/trino.yaml);
  3. dbt: beschrijvingen, lineage, testresultaten (metadata/dbt.yaml); de
     testresultaten komen van de laatste dbt build (/var/lib/dbt/laatste);
  4. Dagster: jobs, runs en lineage (metadata/dagster.yaml).

De ingestie van OpenMetadata heeft eigen afhankelijkheden; die staat daarom in
een eigen virtualenv in het werk-image (/opt/openmetadata), aangeroepen als CLI.
Het token van de ingestion-bot staat in OPENMETADATA_BOT_TOKEN; zonder token
slaat de job over met een melding.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from datetime import datetime, timezone

from dagster import (
    DagsterRunStatus,
    DefaultSensorStatus,
    OpExecutionContext,
    RunRequest,
    SkipReason,
    job,
    op,
    run_status_sensor,
)

HIER = Path(__file__).resolve().parent.parent
CONFIG = HIER / "metadata"
CLI = os.environ.get("OPENMETADATA_CLI", "/opt/openmetadata/bin/metadata")
DBT_UIT = Path(os.environ.get("DBT_UIT", "/var/lib/dbt"))
WORKFLOWS = ["trino", "dbt", "dagster"]


def bewaar_dbt_uitkomst(target_path):
    """Na elke dbt build: run_results en manifest naar een vaste plek, voor de dbt-ingestie."""
    doel = DBT_UIT / "laatste"
    doel.mkdir(parents=True, exist_ok=True)
    for naam in ("run_results.json", "manifest.json"):
        bron = Path(target_path) / naam
        if bron.exists():
            shutil.copyfile(bron, doel / f".{naam}")
            os.replace(doel / f".{naam}", doel / naam)


def workflow_config(naam):
    """De YAML van één workflow, met de gedeelde serverconfiguratie erbij."""
    tekst = (CONFIG / f"{naam}.yaml").read_text() + "\n" + (CONFIG / "_server.yaml").read_text()
    f = tempfile.NamedTemporaryFile("w", suffix=f"-{naam}.yaml", delete=False)  # pylint: disable=consider-using-with
    f.write(tekst)
    f.close()
    return f.name


def draai(context, opdracht, **kw):
    context.log.info("$ " + " ".join(opdracht))
    p = subprocess.run(opdracht, capture_output=True, text=True, check=False, **kw)
    staart = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
    if p.returncode:
        raise RuntimeError(f"{opdracht[0]} faalde ({p.returncode}):\n{staart}")
    context.log.info(staart)


@op
def openmetadata_bijwerken(context: OpExecutionContext):
    if not os.environ.get("OPENMETADATA_BOT_TOKEN"):
        context.log.warning("Geen OPENMETADATA_BOT_TOKEN: OpenMetadata wordt niet bijgewerkt. "
                            "Zie docs/INRICHTING.md, stap OpenMetadata.")
        return
    docs = DBT_UIT / "docs"
    draai(context, ["dbt", "docs", "generate", "--target-path", str(docs), "--quiet"],
          cwd=HIER / "transformatie")
    for naam in WORKFLOWS:
        if naam == "dbt" and not (DBT_UIT / "laatste" / "run_results.json").exists():
            context.log.info("Nog geen dbt build geweest: testresultaten volgen na de eerste keten")
        pad = workflow_config(naam)
        try:
            draai(context, [CLI, "ingest", "-c", pad])
        finally:
            os.unlink(pad)


@job(description="OpenMetadata bijwerken: catalogus (Trino), dbt en Dagster (DF-ADR-007)")
def metadata():
    openmetadata_bijwerken()


def sensor(keten_job):
    @run_status_sensor(run_status=DagsterRunStatus.SUCCESS, monitored_jobs=[keten_job],
                       request_job=metadata, minimum_interval_seconds=60,
                       default_status=DefaultSensorStatus.RUNNING,
                       description="Na een geslaagde keten OpenMetadata bijwerken, hoogstens één keer per uur")
    def na_de_keten(context):  # pylint: disable=unused-argument
        if not os.environ.get("OPENMETADATA_BOT_TOKEN"):
            return SkipReason("Geen OPENMETADATA_BOT_TOKEN")
        # Eén run per uur: Dagster start een run_key maar één keer.
        return RunRequest(run_key=datetime.now(timezone.utc).strftime("metadata-%Y%m%d%H"))

    return na_de_keten
