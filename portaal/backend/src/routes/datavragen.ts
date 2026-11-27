import type { FastifyInstance } from "fastify";
import { AppFout } from "../app.js";
import { vereis } from "../toegang.js";

/** Elke datavraag aan Trino (DF-ADR-016): zoeken op wie, welke tabel en wanneer. */
export async function datavraagRoutes(app: FastifyInstance): Promise<void> {
  const d = app.diensten;

  app.get<{ Querystring: { gebruiker?: string; tabel?: string; van?: string; tot?: string; status?: string; voor?: string } }>(
    "/api/datavragen",
    {
      schema: {
        querystring: {
          type: "object", additionalProperties: false,
          properties: {
            gebruiker: { type: "string", maxLength: 200 },
            tabel: { type: "string", maxLength: 300, pattern: "^[a-z0-9_.]*$" },
            van: { type: "string", format: "date" },
            tot: { type: "string", format: "date" },
            status: { enum: ["FINISHED", "FAILED"] },
            voor: { type: "string", pattern: "^[0-9]+$" },
          },
        },
      },
    },
    async (req) => {
      vereis(req, "datavragen.view");
      const q = req.query;
      const waar: string[] = [];
      const args: unknown[] = [];
      const zet = (sql: string, waarde: unknown) => { args.push(waarde); waar.push(sql.replace("?", `$${args.length}`)); };
      if (q.gebruiker) zet("gebruiker ILIKE ?", `%${q.gebruiker.replace(/[%_\\]/g, "\\$&")}%`);
      if (q.tabel) zet("EXISTS (SELECT 1 FROM jsonb_array_elements(tabellen) t WHERE t->>'tabel' LIKE ?)", `%${q.tabel}%`);
      if (q.van) zet("einde >= ?::date", q.van);
      if (q.tot) zet("einde < ?::date + 1", q.tot);
      if (q.status) zet("status = ?", q.status);
      if (q.voor) zet("id < ?", q.voor);
      const r = await d.pool.query(
        `SELECT id, query_id, gebruiker, bron, client_adres, soort, status, fout, left(sql, 400) AS sql, tabellen, rijen, bytes, begin, einde
           FROM datavragen ${waar.length ? `WHERE ${waar.join(" AND ")}` : ""} ORDER BY id DESC LIMIT 100`,
        args,
      );
      const stand = await d.pool.query(
        "SELECT count(*)::int AS totaal, count(*) FILTER (WHERE einde > now() - interval '24 hours')::int AS vandaag, count(DISTINCT gebruiker)::int AS gebruikers FROM datavragen",
      );
      return { stand: stand.rows[0], vragen: r.rows, meer: r.rows.length === 100 ? r.rows[99].id : null };
    },
  );

  app.get<{ Params: { id: string } }>(
    "/api/datavragen/:id",
    { schema: { params: { type: "object", properties: { id: { type: "string", pattern: "^[0-9]+$" } } } } },
    async (req) => {
      vereis(req, "datavragen.view");
      const r = await d.pool.query("SELECT * FROM datavragen WHERE id = $1", [req.params.id]);
      if (!r.rowCount) throw new AppFout(404, "niet-gevonden", "Deze datavraag bestaat niet.");
      return r.rows[0];
    },
  );
}
