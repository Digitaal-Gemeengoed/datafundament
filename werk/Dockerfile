# Eén image voor de code van het Datafundament: ingestie (dlt), transformatie
# (dbt), orkestratie en inrichting. Dagster (webserver, daemon, code) draait ook hierop.
# Bouwen vanuit de root van de repo: docker build -f werk/Dockerfile .
FROM python:3.13-slim

RUN useradd --create-home --uid 1000 werk
COPY werk/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt
# De ingestie van OpenMetadata in een eigen virtualenv: andere afhankelijkheden
# dan Dagster en dlt. Dagster roept hem aan als CLI (orkestratie/metadata.py).
COPY werk/openmetadata.txt /tmp/openmetadata.txt
RUN python -m venv /opt/openmetadata \
 && /opt/openmetadata/bin/pip install --no-cache-dir -r /tmp/openmetadata.txt

WORKDIR /app
COPY ingestie/ ingestie/
COPY orkestratie/ orkestratie/
COPY beheer/ beheer/
COPY transformatie/ transformatie/
COPY metadata/ metadata/
ENV PYTHONPATH=/app \
    DAGSTER_HOME=/opt/dagster/home \
    DLT_DATA_DIR=/var/lib/dlt \
    DBT_PROFILES_DIR=/app/transformatie

RUN mkdir -p /opt/dagster/home/storage /var/lib/dlt /var/lib/dbt \
 && chown -R werk /opt/dagster /var/lib/dlt /var/lib/dbt /app/transformatie
USER werk

# De DuckDB-extensies vooraf, zodat een run niets hoeft te downloaden.
RUN python -c "import duckdb; [duckdb.install_extension(e) for e in ('httpfs', 'iceberg', 'spatial', 'postgres')]"
# Het manifest van dbt, voor Dagster (lineage en een asset per model).
RUN cd transformatie && rm -rf target && dbt parse --no-partial-parse --quiet
