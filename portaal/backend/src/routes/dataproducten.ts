import type { FastifyInstance } from "fastify";
import { vereis } from "../toegang.js";

/** De lagen van het lakehouse, in de volgorde van de keten. */
export function laag(groep: string): string {
  if (groep === "bron") return "bron";
  if (groep.startsWith("ruw_")) return "ruw";
  if (groep === "uniform") return "uniform";
  if (groep === "dataproduct") return "dataproduct";
  return "overig";
}

export async function dataproductRoutes(app: FastifyInstance): Promise<void> {
  const d = app.diensten;

  /** Alles wat Dagster kent, per laag: bronnen, ruwe lagen, uniforme laag, dataproducten. */
  app.get("/api/dataproducten", async (req) => {
    vereis(req, "dataproducten.view");
    const assets = await d.koppelingen.assets();
    return assets.map((a) => ({ ...a, laag: laag(a.groep) }));
  });
}
