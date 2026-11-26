import type { FastifyInstance } from "fastify";
import { AppFout } from "../app.js";
import { schrijfAudit } from "../audit.js";
import { vereis } from "../toegang.js";

const UUID = { type: "string", pattern: "^[0-9a-fA-F-]{36}$" } as const;
const DATAPRODUCT = { type: "string", pattern: "^[a-z0-9_]+(/[a-z0-9_]+){1,3}$", maxLength: 200 } as const;

/** Een dataproduct als tabel in Trino: dataproduct/x in het lakehouse, dwh/dataproduct/x in PostGIS. */
export function trinoTabel(dataproduct: string): { catalog: string; schema: string; table: string } | null {
  const d = dataproduct.split("/");
  if (d.length === 2) return { catalog: "lakehouse", schema: d[0], table: d[1] };
  if (d.length === 3 && d[0] === "dwh") return { catalog: "dwh", schema: d[1], table: d[2] };
  return null;
}

export async function toegangRoutes(app: FastifyInstance): Promise<void> {
  const d = app.diensten;

  /** Eigen aanvragen; wie mag beoordelen, ziet alles. */
  app.get("/api/toegang", async (req) => {
    const p = req.persoon!;
    if (!p.rechten.has("toegang.beoordelen")) vereis(req, "toegang.aanvragen");
    const r = await d.pool.query(
      `SELECT t.id, t.dataproduct, t.doel, t.grondslag, t.gewenst_tot, t.status, t.toelichting, t.aangemaakt, t.beoordeeld,
              a.id AS aanvrager_id, a.naam AS aanvrager, a.email AS aanvrager_email, b.naam AS beoordelaar
         FROM toegangsaanvragen t JOIN accounts a ON a.id = t.aanvrager LEFT JOIN accounts b ON b.id = t.beoordelaar
        WHERE $1 OR t.aanvrager = $2
        ORDER BY (t.status = 'aangevraagd') DESC, t.aangemaakt DESC LIMIT 500`,
      [p.rechten.has("toegang.beoordelen"), p.id],
    );
    return r.rows.map((t) => ({ ...t, eigen: t.aanvrager_id === p.id, mag_beoordelen: p.rechten.has("toegang.beoordelen") && t.aanvrager_id !== p.id }));
  });

  app.post<{ Body: { dataproduct: string; doel: string; grondslag: string; gewenst_tot?: string } }>(
    "/api/toegang",
    {
      schema: {
        body: {
          type: "object", required: ["dataproduct", "doel", "grondslag"], additionalProperties: false,
          properties: {
            dataproduct: DATAPRODUCT,
            doel: { type: "string", minLength: 10, maxLength: 2000 },
            grondslag: { type: "string", minLength: 3, maxLength: 500 },
            gewenst_tot: { type: "string", format: "date" },
          },
        },
      },
    },
    async (req, antwoord) => {
      vereis(req, "toegang.aanvragen");
      const p = req.persoon!;
      if (!trinoTabel(req.body.dataproduct)) throw new AppFout(400, "geen-dataproduct", "Dat is geen dataproduct.");
      const r = await d.pool.query(
        "INSERT INTO toegangsaanvragen (dataproduct, aanvrager, doel, grondslag, gewenst_tot, aangemaakt) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
        [req.body.dataproduct, p.id, req.body.doel, req.body.grondslag, req.body.gewenst_tot ?? null, d.nu()],
      );
      await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: "toegang.aangevraagd", doel: req.body.dataproduct, ip: req.ip, resultaat: "ok", details: { aanvraag: r.rows[0].id } });
      antwoord.code(201);
      return { id: r.rows[0].id };
    },
  );

  /** Beoordelen: nooit je eigen aanvraag (vier ogen; ook de database weigert het). */
  app.post<{ Params: { id: string }; Body: { besluit: "toegekend" | "afgewezen"; toelichting: string } }>(
    "/api/toegang/:id/beoordeling",
    {
      schema: {
        params: { type: "object", properties: { id: UUID } },
        body: { type: "object", required: ["besluit", "toelichting"], additionalProperties: false, properties: { besluit: { enum: ["toegekend", "afgewezen"] }, toelichting: { type: "string", minLength: 5, maxLength: 2000 } } },
      },
    },
    async (req) => {
      vereis(req, "toegang.beoordelen");
      const p = req.persoon!;
      const t = (await d.pool.query("SELECT aanvrager, status, dataproduct FROM toegangsaanvragen WHERE id = $1", [req.params.id])).rows[0];
      if (!t) throw new AppFout(404, "niet-gevonden", "Deze aanvraag bestaat niet.");
      if (t.aanvrager === p.id) throw new AppFout(403, "eigen-aanvraag", "Je beoordeelt je eigen aanvraag niet.");
      if (t.status !== "aangevraagd") throw new AppFout(409, "al-beoordeeld", "Deze aanvraag is al beoordeeld.");
      await d.pool.query("UPDATE toegangsaanvragen SET status = $2, beoordelaar = $3, beoordeeld = $4, toelichting = $5 WHERE id = $1",
        [req.params.id, req.body.besluit, p.id, d.nu(), req.body.toelichting]);
      await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: `toegang.${req.body.besluit}`, doel: t.dataproduct, ip: req.ip, resultaat: "ok", details: { aanvraag: req.params.id, toelichting: req.body.toelichting } });
      return { status: req.body.besluit };
    },
  );

  /** Intrekken: de aanvrager zolang het nog niet beoordeeld is, een beoordelaar als het al is toegekend. */
  app.post<{ Params: { id: string }; Body: { toelichting: string } }>(
    "/api/toegang/:id/intrekken",
    {
      schema: {
        params: { type: "object", properties: { id: UUID } },
        body: { type: "object", required: ["toelichting"], additionalProperties: false, properties: { toelichting: { type: "string", minLength: 5, maxLength: 2000 } } },
      },
    },
    async (req) => {
      const p = req.persoon!;
      const t = (await d.pool.query("SELECT aanvrager, status, dataproduct FROM toegangsaanvragen WHERE id = $1", [req.params.id])).rows[0];
      if (!t) throw new AppFout(404, "niet-gevonden", "Deze aanvraag bestaat niet.");
      const eigen = t.aanvrager === p.id && t.status === "aangevraagd";
      const beoordelaar = p.rechten.has("toegang.beoordelen") && t.aanvrager !== p.id && t.status === "toegekend";
      if (!eigen && !beoordelaar) throw new AppFout(403, "geen-recht", "Daarvoor heb je geen recht.");
      if (eigen) {
        // Ook een eigen intrekking telt als afronding; beoordelaar blijft leeg kan niet (vier ogen), dus de aanvrager tekent zelf af.
        await d.pool.query("UPDATE toegangsaanvragen SET status = 'ingetrokken', beoordeeld = $2, toelichting = $3 WHERE id = $1", [req.params.id, d.nu(), req.body.toelichting]);
      } else {
        await d.pool.query("UPDATE toegangsaanvragen SET status = 'ingetrokken', toelichting = $2 WHERE id = $1", [req.params.id, req.body.toelichting]);
      }
      await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: "toegang.ingetrokken", doel: t.dataproduct, ip: req.ip, resultaat: "ok", details: { aanvraag: req.params.id, toelichting: req.body.toelichting } });
      return { status: "ingetrokken" };
    },
  );

  /**
   * De toekenningen als regels voor Trino (file-based access control, DF-ADR-008).
   * Tot Trino via Keycloak inlogt, is dit een voorstel om in Git te zetten.
   */
  app.get("/api/toegang/regels", async (req) => {
    vereis(req, "toegang.beoordelen");
    const r = await d.pool.query(
      `SELECT a.email, t.dataproduct FROM toegangsaanvragen t JOIN accounts a ON a.id = t.aanvrager
        WHERE t.status = 'toegekend' AND (t.gewenst_tot IS NULL OR t.gewenst_tot >= $1::date) ORDER BY a.email, t.dataproduct`,
      [d.nu()],
    );
    const tables = r.rows
      .map((x) => ({ x, t: trinoTabel(x.dataproduct) }))
      .filter((y) => y.t)
      .map(({ x, t }) => ({ user: x.email.replace(/[.^$*+?()[\]{}|\\]/g, "\\$&"), ...t!, privileges: ["SELECT"] }));
    return { tables: [...tables, { privileges: [] }] };
  });
}
