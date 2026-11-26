import type { FastifyInstance } from "fastify";
import { AppFout } from "../app.js";
import { schrijfAudit } from "../audit.js";
import { bsnHmac, geldigBsn } from "../kluis.js";
import { vereis } from "../toegang.js";

const UUID = { type: "string", pattern: "^[0-9a-fA-F-]{36}$" } as const;
const KLAAR: Record<string, "uitgevoerd" | "mislukt"> = { SUCCESS: "uitgevoerd", FAILURE: "mislukt", CANCELED: "mislukt" };

/**
 * Verwijderverzoeken (DF-ADR-015): vastleggen, beoordelen door een tweede
 * persoon, uitvoeren door de job verwijderen in Dagster, en het bewijs
 * bewaren. Het BSN wordt alleen omgezet in de HMAC van de kluis.
 */
export async function verwijderRoutes(app: FastifyInstance): Promise<void> {
  const d = app.diensten;

  function kluis(): string {
    if (!d.config.kluisGeheim) throw new AppFout(503, "geen-kluis", "Verwijderverzoeken staan uit: KLUIS_GEHEIM ontbreekt.");
    return d.config.kluisGeheim;
  }

  /** Lopende uitvoeringen bijwerken met de stand in Dagster. */
  async function werkBij(): Promise<void> {
    const lopend = (await d.pool.query("SELECT id, dagster_run FROM verwijderverzoeken WHERE status = 'in-uitvoering' AND dagster_run IS NOT NULL")).rows;
    for (const v of lopend) {
      const s = await d.koppelingen.runStand(v.dagster_run).catch(() => null);
      const nieuw = s && KLAAR[s.status];
      if (!nieuw) continue;
      await d.pool.query("UPDATE verwijderverzoeken SET status = $2, afgerond = $3, bewijs = $4 WHERE id = $1 AND status = 'in-uitvoering'",
        [v.id, nieuw, d.nu(), JSON.stringify({ run: v.dagster_run, dagster: s.status, ...(s.bewijs ?? {}) })]);
      await schrijfAudit(d.pool, { actie: `verwijderen.${nieuw}`, doel: v.id, resultaat: "ok", details: { run: v.dagster_run, ...(s.bewijs ?? {}) } });
    }
  }

  app.get("/api/verwijderverzoeken", async (req) => {
    const p = req.persoon!;
    if (!p.rechten.has("verwijderen.beoordelen")) vereis(req, "verwijderen.aanvragen");
    await werkBij();
    const r = await d.pool.query(
      `SELECT v.id, v.bsn_einde, v.grondslag, v.reden, v.status, v.aangemaakt, v.beoordeeld, v.toelichting, v.dagster_run, v.afgerond, v.bewijs,
              a.id AS aanvrager_id, a.naam AS aanvrager, b.naam AS beoordelaar
         FROM verwijderverzoeken v JOIN accounts a ON a.id = v.aanvrager LEFT JOIN accounts b ON b.id = v.beoordelaar
        ORDER BY (v.status IN ('aangevraagd', 'in-uitvoering', 'mislukt')) DESC, v.aangemaakt DESC LIMIT 500`,
    );
    return {
      aan: d.config.kluisGeheim !== null,
      verzoeken: r.rows.map((v) => ({ ...v, bsn: `******${v.bsn_einde}`, mag_beoordelen: p.rechten.has("verwijderen.beoordelen") && v.aanvrager_id !== p.id })),
    };
  });

  app.post<{ Body: { bsn: string; grondslag: string; reden: string } }>(
    "/api/verwijderverzoeken",
    {
      schema: {
        body: {
          type: "object", required: ["bsn", "grondslag", "reden"], additionalProperties: false,
          properties: {
            bsn: { type: "string", pattern: "^[0-9]{9}$" },
            grondslag: { enum: ["avg-art17", "bewaartermijn", "onrechtmatig", "overig"] },
            reden: { type: "string", minLength: 10, maxLength: 2000 },
          },
        },
      },
    },
    async (req, antwoord) => {
      vereis(req, "verwijderen.aanvragen");
      const p = req.persoon!;
      if (!geldigBsn(req.body.bsn)) throw new AppFout(400, "ongeldig-bsn", "Dit BSN voldoet niet aan de elfproef.");
      const hmac = bsnHmac(req.body.bsn, kluis());
      const dubbel = await d.pool.query("SELECT 1 FROM verwijderverzoeken WHERE bsn_hmac = $1 AND status IN ('aangevraagd', 'in-uitvoering')", [hmac]);
      if (dubbel.rowCount) throw new AppFout(409, "loopt-al", "Voor dit BSN loopt al een verzoek.");
      const r = await d.pool.query(
        "INSERT INTO verwijderverzoeken (bsn_hmac, bsn_einde, grondslag, reden, aanvrager, aangemaakt) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
        [hmac, req.body.bsn.slice(-3), req.body.grondslag, req.body.reden, p.id, d.nu()],
      );
      await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: "verwijderen.aangevraagd", doel: r.rows[0].id, ip: req.ip, resultaat: "ok", details: { bsn_einde: req.body.bsn.slice(-3), grondslag: req.body.grondslag } });
      antwoord.code(201);
      return { id: r.rows[0].id };
    },
  );

  async function start(id: string): Promise<string> {
    const v = (await d.pool.query("SELECT encode(bsn_hmac, 'hex') AS hmac FROM verwijderverzoeken WHERE id = $1", [id])).rows[0];
    return d.koppelingen.startVerwijderen(id, v.hmac);
  }

  /** Beoordelen door een tweede persoon; bij goedkeuring start de job meteen. */
  app.post<{ Params: { id: string }; Body: { besluit: "goedgekeurd" | "afgewezen"; toelichting: string } }>(
    "/api/verwijderverzoeken/:id/beoordeling",
    {
      schema: {
        params: { type: "object", properties: { id: UUID } },
        body: { type: "object", required: ["besluit", "toelichting"], additionalProperties: false, properties: { besluit: { enum: ["goedgekeurd", "afgewezen"] }, toelichting: { type: "string", minLength: 5, maxLength: 2000 } } },
      },
    },
    async (req) => {
      vereis(req, "verwijderen.beoordelen");
      const p = req.persoon!;
      kluis();
      const v = (await d.pool.query("SELECT aanvrager, status FROM verwijderverzoeken WHERE id = $1", [req.params.id])).rows[0];
      if (!v) throw new AppFout(404, "niet-gevonden", "Dit verzoek bestaat niet.");
      if (v.aanvrager === p.id) throw new AppFout(403, "eigen-verzoek", "Je beoordeelt je eigen verzoek niet.");
      if (v.status !== "aangevraagd") throw new AppFout(409, "al-beoordeeld", "Dit verzoek is al beoordeeld.");
      if (req.body.besluit === "afgewezen") {
        await d.pool.query("UPDATE verwijderverzoeken SET status = 'afgewezen', beoordelaar = $2, beoordeeld = $3, toelichting = $4 WHERE id = $1",
          [req.params.id, p.id, d.nu(), req.body.toelichting]);
        await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: "verwijderen.afgewezen", doel: req.params.id, ip: req.ip, resultaat: "ok", details: { toelichting: req.body.toelichting } });
        return { status: "afgewezen" };
      }
      // Eerst starten; pas als Dagster de run heeft, ligt het besluit vast.
      const run = await start(req.params.id);
      await d.pool.query("UPDATE verwijderverzoeken SET status = 'in-uitvoering', beoordelaar = $2, beoordeeld = $3, toelichting = $4, dagster_run = $5 WHERE id = $1",
        [req.params.id, p.id, d.nu(), req.body.toelichting, run]);
      await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: "verwijderen.goedgekeurd", doel: req.params.id, ip: req.ip, resultaat: "ok", details: { run, toelichting: req.body.toelichting } });
      return { status: "in-uitvoering", run };
    },
  );

  /** Een mislukte uitvoering opnieuw starten (de job is herhaalbaar). */
  app.post<{ Params: { id: string } }>(
    "/api/verwijderverzoeken/:id/opnieuw",
    { schema: { params: { type: "object", properties: { id: UUID } } } },
    async (req) => {
      vereis(req, "verwijderen.beoordelen");
      const p = req.persoon!;
      kluis();
      const v = (await d.pool.query("SELECT aanvrager, status FROM verwijderverzoeken WHERE id = $1", [req.params.id])).rows[0];
      if (!v) throw new AppFout(404, "niet-gevonden", "Dit verzoek bestaat niet.");
      if (v.aanvrager === p.id) throw new AppFout(403, "eigen-verzoek", "Je voert je eigen verzoek niet uit.");
      if (v.status !== "mislukt") throw new AppFout(409, "niet-mislukt", "Alleen een mislukte uitvoering kan opnieuw.");
      const run = await start(req.params.id);
      await d.pool.query("UPDATE verwijderverzoeken SET status = 'in-uitvoering', dagster_run = $2, afgerond = NULL, bewijs = NULL WHERE id = $1", [req.params.id, run]);
      await schrijfAudit(d.pool, { account: p.id, email: p.email, actie: "verwijderen.opnieuw", doel: req.params.id, ip: req.ip, resultaat: "ok", details: { run } });
      return { status: "in-uitvoering", run };
    },
  );
}
