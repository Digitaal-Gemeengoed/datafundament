"""De publicaties voor CDC: per bron één, met per tabel de kolommen (DF-ADR-006).

    python publicaties.py          publicaties bijwerken (na elke schemawijziging)
    python publicaties.py status   publicaties en slots

Elke databasebron krijgt een publicatie `df_<schema>`. Die noemt per tabel welke
kolommen meegaan: alles, behalve namen en A-nummers. Die verlaten de bron dus
nooit, ook niet via de replicatie (zie DF-ADR-015). Het BSN gaat wel mee: dat
vervangt de ingestie op dfc door een pseudoniem.

Alleen tabellen met een primaire sleutel; zonder kan PostgreSQL een UPDATE of
DELETE niet repliceren (en weigert hij die). TRUNCATE wordt niet gepubliceerd.

Een nieuwe kolom komt pas door als deze publicatie is bijgewerkt. Dat is
bewust: een nieuwe kolom met persoonsgegevens glipt er niet vanzelf in.

WEG moet dezelfde kolommen noemen als REGELS in ingestie/pseudoniem.py (of meer);
ingestie/test_cdc.py controleert dat.
"""

import sys

SCHEMAS = ["brp", "bag", "woz", "mor", "sociaal"]
WEG = {"a_nummer", "vorig_a_nummer", "volgend_a_nummer", "voornamen", "voorvoegsel_geslachtsnaam",
       "geslachtsnaam", "adellijke_titel_predikaat"}


def tabellen(cur, schema):
    """(tabel, kolommen) van de tabellen met een primaire sleutel, zonder de kolommen in WEG."""
    cur.execute("""
        SELECT c.relname, array_agg(a.attname ORDER BY a.attnum)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE n.nspname = %s AND c.relkind = 'r'
          AND EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid = c.oid AND i.indisprimary)
        GROUP BY c.relname ORDER BY c.relname""", (schema,))
    return [(t, [k for k in kolommen if k not in WEG]) for t, kolommen in cur.fetchall()]


def zet(cur, schemas=SCHEMAS):
    """Maakt of werkt de publicaties df_<schema> bij. Geeft {schema: aantal tabellen}."""
    from psycopg import sql  # pylint: disable=import-outside-toplevel
    uit = {}
    for schema in schemas:
        t = tabellen(cur, schema)
        naam = sql.Identifier(f"df_{schema}")
        cur.execute("SELECT 1 FROM pg_publication WHERE pubname = %s", (f"df_{schema}",))
        bestaat = cur.fetchone() is not None
        if not t:
            if bestaat:
                cur.execute(sql.SQL("DROP PUBLICATION {}").format(naam))
            uit[schema] = 0
            continue
        lijst = sql.SQL(", ").join(
            sql.SQL("{} ({})").format(sql.Identifier(schema, tabel), sql.SQL(", ").join(map(sql.Identifier, k)))
            for tabel, k in t)
        if bestaat:
            cur.execute(sql.SQL("ALTER PUBLICATION {} SET TABLE {}").format(naam, lijst))
        else:
            cur.execute(sql.SQL("CREATE PUBLICATION {} FOR TABLE {} WITH (publish = 'insert, update, delete')")
                        .format(naam, lijst))
        uit[schema] = len(t)
    # De oude publicatie voor het hele schema (zonder kolomlijst) is niet meer nodig.
    cur.execute("DROP PUBLICATION IF EXISTS datafundament")
    return uit


def status(cur):
    cur.execute("SELECT pubname, count(*) FROM pg_publication p LEFT JOIN pg_publication_tables t USING (pubname) "
                "GROUP BY 1 ORDER BY 1")
    for naam, n in cur.fetchall():
        print(f"  publicatie {naam}: {n} tabellen")
    cur.execute("SELECT slot_name, active, confirmed_flush_lsn, "
                "pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) "
                "FROM pg_replication_slots ORDER BY 1")
    for naam, actief, lsn, achter in cur.fetchall():
        print(f"  slot {naam}: tot {lsn}, {achter} WAL vastgehouden{' (actief)' if actief else ''}")


def main(args):
    import psycopg  # pylint: disable=import-outside-toplevel
    with psycopg.connect(autocommit=False) as con, con.cursor() as cur:
        if args and args[0] == "status":
            status(cur)
            return
        for schema, n in zet(cur).items():
            print(f"  df_{schema}: {n} tabellen")
        con.commit()


if __name__ == "__main__":
    main(sys.argv[1:])
