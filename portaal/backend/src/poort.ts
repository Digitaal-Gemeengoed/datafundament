/**
 * Wie door de poort mag: de e-mailadressen voor oauth2-proxy (DF-ADR-018).
 *
 * Dagster en de Iceberg-catalogus (Lakekeeper) hebben geen eigen inlog met
 * Keycloak. Caddy vraagt bij elke aanvraag aan oauth2-proxy of de bezoeker via
 * Keycloak is ingelogd en op deze lijst staat. Het portaal schrijft de lijst:
 * actieve accounts met het recht platform.bedienen, of superadmin. oauth2-proxy
 * leest het bestand opnieuw zodra het verandert.
 */
import { rename, writeFile } from "node:fs/promises";
import type pg from "pg";

export async function bouwLijst(pool: pg.Pool): Promise<string[]> {
  const r = await pool.query(
    `SELECT DISTINCT a.email FROM accounts a JOIN lidmaatschappen l ON l.account = a.id JOIN groepen g ON g.id = l.groep
      WHERE a.status = 'actief' AND NOT a.hoofdaccount AND (g.superadmin OR 'platform.bedienen' = ANY (g.rechten))
      ORDER BY 1`);
  return r.rows.map((x) => x.email as string);
}

export class PoortSchrijver {
  private vorige: string | null = null;
  constructor(private pool: pg.Pool, private pad: string) {}

  async schrijf(): Promise<boolean> {
    const tekst = (await bouwLijst(this.pool)).join("\n") + "\n";
    if (tekst === this.vorige) return false;
    await writeFile(`${this.pad}.nieuw`, tekst, { mode: 0o644 });
    await rename(`${this.pad}.nieuw`, this.pad);
    this.vorige = tekst;
    return true;
  }
}
