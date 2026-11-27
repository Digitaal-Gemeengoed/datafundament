/**
 * De regels voor Trino, uit de toekenningen in het portaal (DF-ADR-017).
 *
 * Trino logt in via Keycloak; de gebruiker is het e-mailadres. Wie wat mag, staat
 * in een JSON-bestand (file-based access control) dat Trino elke minuut opnieuw
 * leest. Het portaal schrijft dat bestand, elke 30 seconden als er iets veranderde:
 *
 *   - de dienstgebruiker van OpenMetadata en wie het recht lagen.lezen heeft
 *     (data-engineers): alles lezen;
 *   - wie een toekenning heeft: dat dataproduct lezen. Kolommen met in dbt het
 *     label persoonsgegeven of bijzonder (meta.privacy) zijn gemaskeerd, tenzij de
 *     toekenning 'met persoonsgegevens' is;
 *   - verder niemand iets. Ook zonder manifest van dbt: dan is niet bekend welke
 *     kolommen gevoelig zijn, en geldt alleen een toekenning met persoonsgegevens.
 */
import { readFile, rename, writeFile } from "node:fs/promises";
import type pg from "pg";

/** Een dataproduct als tabel in Trino: dataproduct/x in het lakehouse, dwh/dataproduct/x in PostGIS. */
export function trinoTabel(dataproduct: string): { catalog: string; schema: string; table: string } | null {
  const d = dataproduct.split("/");
  if (d.length === 2) return { catalog: "lakehouse", schema: d[0], table: d[1] };
  if (d.length === 3 && d[0] === "dwh") return { catalog: "dwh", schema: d[1], table: d[2] };
  return null;
}

export const DIENSTGEBRUIKERS = ["openmetadata"];
const LABELS = new Set(["persoonsgegeven", "bijzonder"]);

export interface Tabel { catalog: string; schema: string; table: string; gevoelig: string[] }

/** Per dataproduct (zoals in het portaal: dataproduct/x, dwh/dataproduct/x) de gevoelige kolommen. */
export function uitManifest(manifest: { nodes?: Record<string, any> }): Map<string, Tabel> {
  const uit = new Map<string, Tabel>();
  for (const n of Object.values(manifest.nodes ?? {})) {
    if (n.resource_type !== "model") continue;
    const config = n.config ?? {};
    const schema = config.schema ?? n.schema;
    const naam = n.alias ?? n.name;
    const dwh = config.database === "dwh";
    const sleutel = dwh ? `dwh/${schema}/${naam}` : `${schema}/${naam}`;
    const t = trinoTabel(sleutel);
    if (!t) continue;
    const gevoelig = Object.values<any>(n.columns ?? {})
      .filter((k) => LABELS.has(k.meta?.privacy ?? k.config?.meta?.privacy))
      .map((k) => String(k.name).toLowerCase())
      .sort();
    uit.set(sleutel, { ...t, gevoelig });
  }
  return uit;
}

const regex = (s: string) => s.replace(/[.^$*+?()[\]{}|\\]/g, "\\$&");
const wie = (namen: string[]) => `^(${namen.map(regex).join("|")})$`;

export async function bouwRegels(pool: pg.Pool, nu: Date, tabellen: Map<string, Tabel> | null): Promise<object> {
  const lezers = (await pool.query(
    `SELECT DISTINCT a.email FROM accounts a JOIN lidmaatschappen l ON l.account = a.id JOIN groepen g ON g.id = l.groep
      WHERE a.status = 'actief' AND 'lagen.lezen' = ANY (g.rechten) ORDER BY 1`)).rows.map((r) => r.email as string);
  const toekenningen = (await pool.query(
    `SELECT a.email, t.dataproduct, bool_or(t.met_persoonsgegevens) AS met
       FROM toegangsaanvragen t JOIN accounts a ON a.id = t.aanvrager
      WHERE t.status = 'toegekend' AND a.status = 'actief' AND (t.gewenst_tot IS NULL OR t.gewenst_tot >= $1::date)
      GROUP BY a.email, t.dataproduct ORDER BY a.email, t.dataproduct`, [nu])).rows;

  const tables: object[] = [
    // Wat elke client nodig heeft om rond te kijken (DBeaver, JDBC).
    { catalog: "system", schema: "(jdbc|metadata)", privileges: ["SELECT"] },
    { user: wie([...DIENSTGEBRUIKERS, ...lezers]), catalog: "(lakehouse|dwh)", privileges: ["SELECT"] },
  ];
  for (const t of toekenningen) {
    const tabel = tabellen?.get(t.dataproduct) ?? null;
    const plek = tabel ?? trinoTabel(t.dataproduct);
    if (!plek) continue;
    if (!t.met && !tabel) continue; // onbekend welke kolommen gevoelig zijn: niet openzetten
    const regel: Record<string, unknown> = {
      user: wie([t.email]), catalog: regex(plek.catalog), schema: regex(plek.schema), table: regex(plek.table),
      privileges: ["SELECT"],
    };
    if (!t.met && tabel!.gevoelig.length) regel.columns = tabel!.gevoelig.map((name) => ({ name, mask: "NULL" }));
    tables.push(regel);
  }
  tables.push({ privileges: [] });

  return {
    catalogs: [
      { catalog: "(lakehouse|dwh|system)", allow: "read-only" },
      { allow: "none" },
    ],
    schemas: [{ owner: false }],
    tables,
    queries: [{ allow: ["execute"] }],
  };
}

/** Schrijft de regels als ze veranderd zijn (atomair: eerst een tijdelijk bestand). */
export class RegelSchrijver {
  private vorige = "";
  constructor(private pool: pg.Pool, private pad: string, private manifest: string, private nu: () => Date) {}

  async tabellen(): Promise<Map<string, Tabel> | null> {
    try {
      return uitManifest(JSON.parse(await readFile(this.manifest, "utf8")));
    } catch {
      return null;
    }
  }

  async schrijf(): Promise<boolean> {
    const tekst = JSON.stringify(await bouwRegels(this.pool, this.nu(), await this.tabellen()), null, 2) + "\n";
    if (tekst === this.vorige) return false;
    await writeFile(`${this.pad}.nieuw`, tekst, { mode: 0o644 });
    await rename(`${this.pad}.nieuw`, this.pad);
    this.vorige = tekst;
    return true;
  }
}
