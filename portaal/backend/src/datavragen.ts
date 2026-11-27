import { timingSafeEqual } from "node:crypto";
import Fastify, { type FastifyInstance } from "fastify";
import type pg from "pg";

/**
 * De ontvanger van Trino (DF-ADR-016). Trino stuurt na elke query een
 * QueryCompletedEvent (HTTP event listener) naar een interne poort van het
 * portaal; die komt niet via Caddy en vraagt een gedeeld token. Wat we
 * bewaren: wie, wanneer, welke tabellen en kolommen, de SQL, en hoeveel.
 */

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

export interface Datavraag {
  query_id: string; gebruiker: string; principal: string | null; bron: string | null; client_adres: string | null;
  soort: string | null; status: string; fout: string | null; sql: string;
  tabellen: { tabel: string; kolommen: string[] }[]; rijen: number | null; bytes: number | null;
  begin: string | null; einde: string | null;
}

const MAX_SQL = 100_000;

/** Een gebeurtenis van Trino omzetten; null als het geen afgeronde query is. */
export function uitGebeurtenis(e: Json): Datavraag | null {
  const m: Json = e?.metadata ?? {};
  const c: Json = e?.context ?? {};
  if (!m.queryId || !e?.statistics) return null; // alleen QueryCompletedEvent
  const tabellen = new Map<string, Set<string>>();
  const voeg = (cat?: string, schema?: string, tabel?: string, kolommen: unknown[] = []) => {
    if (!cat || !schema || !tabel) return;
    const k = `${cat}.${schema}.${tabel}`;
    const s = tabellen.get(k) ?? new Set<string>();
    for (const kol of kolommen) {
      const naam = typeof kol === "string" ? kol : (kol as Json)?.column ?? (kol as Json)?.name;
      if (typeof naam === "string") s.add(naam);
    }
    tabellen.set(k, s);
  };
  for (const i of e.ioMetadata?.inputs ?? []) voeg(i.catalogName, i.schema, i.table, i.columns);
  for (const t of m.tables ?? []) if (t.directlyReferenced !== false) voeg(t.catalog, t.schema, t.table, t.columns);
  const sql = String(m.query ?? "");
  return {
    query_id: String(m.queryId),
    gebruiker: String(c.user ?? "onbekend"),
    principal: c.principal ?? null,
    bron: c.source ?? c.userAgent ?? null,
    client_adres: c.remoteClientAddress ?? null,
    soort: c.queryType ?? null,
    status: String(m.queryState ?? (e.failureInfo ? "FAILED" : "FINISHED")),
    fout: e.failureInfo ? String(e.failureInfo.failureMessage ?? e.failureInfo.errorCode?.name ?? "fout").slice(0, 2000) : null,
    sql: sql.length > MAX_SQL ? `${sql.slice(0, MAX_SQL)}\n-- (ingekort)` : sql,
    tabellen: [...tabellen].map(([tabel, k]) => ({ tabel, kolommen: [...k].sort() })).sort((a, b) => a.tabel.localeCompare(b.tabel)),
    rijen: Number.isFinite(Number(e.statistics?.outputRows)) ? Number(e.statistics.outputRows) : null,
    bytes: Number.isFinite(Number(e.statistics?.totalBytes)) ? Number(e.statistics.totalBytes) : null,
    begin: e.executionStartTime ?? e.createTime ?? null,
    einde: e.endTime ?? null,
  };
}

export async function legVast(pool: pg.Pool, v: Datavraag): Promise<boolean> {
  const r = await pool.query(
    `INSERT INTO datavragen (query_id, gebruiker, principal, bron, client_adres, soort, status, fout, sql, tabellen, rijen, bytes, begin, einde)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) ON CONFLICT (query_id) DO NOTHING`,
    [v.query_id, v.gebruiker, v.principal, v.bron, v.client_adres, v.soort, v.status, v.fout, v.sql, JSON.stringify(v.tabellen), v.rijen, v.bytes, v.begin, v.einde],
  );
  return (r.rowCount ?? 0) > 0;
}

/** De interne ontvanger: alleen POST /trino/gebeurtenis, met het token als kop. */
export function ontvanger(pool: pg.Pool, token: string): FastifyInstance {
  const app = Fastify({ logger: { level: "warn" }, bodyLimit: 8 * 1024 * 1024 });
  const verwacht = Buffer.from(token);
  app.post("/trino/gebeurtenis", async (req, antwoord) => {
    const gekregen = Buffer.from(String(req.headers["x-datavragen-token"] ?? ""));
    if (gekregen.length !== verwacht.length || !timingSafeEqual(gekregen, verwacht)) return antwoord.code(401).send();
    const v = uitGebeurtenis(req.body as Json);
    if (v) await legVast(pool, v);
    return antwoord.code(204).send();
  });
  app.get("/gezond", async () => ({ ok: true }));
  return app;
}
