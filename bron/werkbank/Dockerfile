# Werkbank voor de bron: brp.py met de PostgreSQL-driver.
FROM python:3.13-slim
RUN pip install --no-cache-dir --root-user-action=ignore "psycopg[binary]==3.3.9"
WORKDIR /werk
COPY brp.py .
ENTRYPOINT ["python", "brp.py"]
