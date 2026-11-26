# Eén image voor de code van het Datafundament: ingestie, transformatie,
# orkestratie en inrichting. Dagster (webserver, daemon, code) draait ook hierop.
# Bouwen vanuit de root van de repo: docker build -f werk/Dockerfile .
FROM python:3.13-slim

RUN useradd --create-home --uid 1000 werk
COPY werk/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt

WORKDIR /app
COPY ingestie/ ingestie/
COPY orkestratie/ orkestratie/
COPY beheer/ beheer/
ENV PYTHONPATH=/app \
    DAGSTER_HOME=/opt/dagster/home \
    DLT_DATA_DIR=/var/lib/dlt

RUN mkdir -p /opt/dagster/home/storage /var/lib/dlt && chown -R werk /opt/dagster /var/lib/dlt
USER werk
