"""Een DuckDB-verbinding met het lakehouse (Iceberg via Lakekeeper) die mag schrijven.

Dezelfde ATTACH als in transformatie/profiles.yml en proeven/iceberg-schrijfpad.
"""

import os

import duckdb


def verbind():
    con = duckdb.connect()
    for ext in ("httpfs", "iceberg"):
        con.load_extension(ext)
    con.execute(f"""CREATE SECRET garage (TYPE s3, KEY_ID '{os.environ["GARAGE_SCHRIJVER_SLEUTEL"]}',
        SECRET '{os.environ["GARAGE_SCHRIJVER_GEHEIM"]}', ENDPOINT 'garage:3900', URL_STYLE 'path',
        USE_SSL false, REGION 'garage')""")
    # Lakekeeper vraagt een token van Keycloak: service-account df-lk-werk (DF-ADR-019).
    con.execute(f"""CREATE SECRET lakekeeper (TYPE iceberg, CLIENT_ID 'df-lk-werk',
        CLIENT_SECRET '{os.environ["LK_WERK_GEHEIM"]}', OAUTH2_SCOPE 'lakekeeper',
        OAUTH2_SERVER_URI '{os.environ["PYICEBERG_CATALOG__DEFAULT__OAUTH2_SERVER_URI"]}')""")
    con.execute("""ATTACH 'datafundament' AS lakehouse (TYPE iceberg, ENDPOINT 'http://lakekeeper:8181/catalog',
        SECRET lakekeeper, ACCESS_DELEGATION_MODE 'none')""")
    return con


def tabellen(con, schema_voorvoegsels):
    """(schema, tabel, kolommen) van de Iceberg-tabellen in schema's met een van de voorvoegsels."""
    rijen = con.execute("SELECT schema_name, table_name, column_name FROM duckdb_columns() "
                        "WHERE database_name = 'lakehouse' ORDER BY 1, 2").fetchall()
    uit = {}
    for schema, tabel, kolom in rijen:
        if any(schema == v or schema.startswith(v + "_") for v in schema_voorvoegsels):
            uit.setdefault((schema, tabel), set()).add(kolom)
    return uit
