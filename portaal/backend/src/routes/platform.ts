import type { FastifyInstance } from "fastify";
import { vereis } from "../toegang.js";

/**
 * Wanneer een ruwe laag "verouderd" is. De ingestie draait elke 5 minuten, dus
 * meestal na een half uur zonder update. Een bron die één bestand per nacht
 * aanlevert (de export van de belastingen, DF-ADR-014) pas na 26 uur: een dag
 * en wat speling.
 */
const VERS_MINUTEN = 30;
const NACHT_MINUTEN = 26 * 60;
const PER_NACHT = (process.env.VERSHEID_PER_NACHT ?? "ruw_belastingen").split(",").map((x) => x.trim()).filter(Boolean);
export function norm(laag: string): { minuten: number; ritme: "vijf-minuten" | "nacht" } {
  const bron = laag.replace(/_stand$/, "");
  return PER_NACHT.includes(bron) ? { minuten: NACHT_MINUTEN, ritme: "nacht" } : { minuten: VERS_MINUTEN, ritme: "vijf-minuten" };
}

export async function platformRoutes(app: FastifyInstance): Promise<void> {
  const d = app.diensten;

  /** De stand van het platform: onderdelen, laatste runs en de versheid per bron. */
  app.get("/api/platform", async (req) => {
    vereis(req, "platform.view");
    const [onderdelen, runs, assets] = await Promise.all([
      d.koppelingen.gezondheid(),
      d.koppelingen.runs(25).catch(() => null),
      d.koppelingen.assets().catch(() => null),
    ]);
    const nu = d.nu().getTime();
    const bronnen = new Map<string, { laag: string; laatst: number | null; tabellen: number }>();
    for (const a of assets ?? []) {
      if (!a.groep.startsWith("ruw_")) continue;
      const b = bronnen.get(a.groep) ?? { laag: a.groep, laatst: null, tabellen: 0 };
      b.tabellen += 1;
      if (a.laatst && (b.laatst === null || a.laatst > b.laatst)) b.laatst = a.laatst;
      bronnen.set(a.groep, b);
    }
    return {
      onderdelen,
      runs,
      versheid: [...bronnen.values()]
        .sort((x, y) => x.laag.localeCompare(y.laag))
        .map((b) => {
          const n = norm(b.laag);
          return { ...b, ritme: n.ritme, stand: b.laatst === null ? "nooit" : nu - b.laatst > n.minuten * 60_000 ? "verouderd" : "vers" };
        }),
    };
  });
}
