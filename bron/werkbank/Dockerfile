# Werkbank voor de bron: laden, synthetische bronnen, simulatie, export (brp.py),
# en de Zaken-API (zaken_api.py). Zelfde image, ander startcommando.
FROM python:3.13-slim
RUN pip install --no-cache-dir --root-user-action=ignore "psycopg[binary]==3.3.9" "fastapi==0.121.3" \
    "uvicorn==0.38.0" "boto3==1.40.76" "tzdata==2026.6"
WORKDIR /werk
COPY *.py *.sql ./
ENTRYPOINT ["python", "brp.py"]
