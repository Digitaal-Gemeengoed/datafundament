FROM python:3.13-slim
RUN pip install --no-cache-dir --root-user-action=ignore \
      "dlt[sql_database,postgres,pyiceberg,s3]==1.32.0" psycopg2-binary
WORKDIR /werk
COPY proef.py .
CMD ["python", "proef.py"]
