import type { FastifyInstance } from "fastify";
import { vereis } from "../toegang.js";

/** Een ruwe laag die langer dan dit niet is bijgewerkt, staat op "verouderd" (de ingestie draait elke 5 minuten). */
const VERS_MINUTEN = 30;

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
        .map((b) => ({ ...b, stand: b.laatst === null ? "nooit" : nu - b.laatst > VERS_MINUTEN * 60_000 ? "verouderd" : "vers" })),
    };
  });
}
