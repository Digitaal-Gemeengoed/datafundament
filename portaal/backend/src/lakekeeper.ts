/**
 * Rechten van mensen in Lakekeeper, uit het portaal (DF-ADR-020).
 *
 * Lakekeeper logt in via Keycloak en houdt de rechten bij in OpenFGA (DF-ADR-019).
 * Een mens is daar `oidc~<id in Keycloak>`. Het portaal zet elke 30 seconden:
 *
 *   - wie het recht platform.bedienen heeft: `describe` op het project, dus
 *     warehouses, namespaces, tabellen en snapshots zien, geen data;
 *   - superadmin: `project_admin`, dus ook beheren en rechten geven.
 *
 * Wie het recht verliest, of geblokkeerd of gedeactiveerd wordt, verliest het ook
 * in Lakekeeper. Het portaal trekt alleen in wat het zelf gaf (tabel
 * lakekeeper_toewijzingen): wat het installatiescript zette, blijft.
 * Het hoofdaccount logt niet in via Keycloak en krijgt niets.
 *
 * Het portaal meldt zich bij Lakekeeper met het service-account df-lk-beheer.
 */
import type pg from "pg";

export type Recht = "describe" | "project_admin";
export interface LakekeeperInstelling {
  url: string;
  /** Het token-adres van de realm, binnen het compose-netwerk. */
  tokenUrl: string;
  clientId: string;
  geheim: string;
}
type Fetch = typeof fetch;

/** Wie wat hoort te hebben, per e-mailadres (met het id in Keycloak als dat bekend is). */
export async function gewenst(pool: pg.Pool): Promise<{ email: string; sub: string | null; recht: Recht }[]> {
  const r = await pool.query(
    `SELECT a.email, a.keycloak_sub, bool_or(g.superadmin) AS superadmin
       FROM accounts a JOIN lidmaatschappen l ON l.account = a.id JOIN groepen g ON g.id = l.groep
      WHERE a.status = 'actief' AND NOT a.hoofdaccount AND (g.superadmin OR 'platform.bedienen' = ANY (g.rechten))
      GROUP BY a.id ORDER BY a.email`);
  return r.rows.map((x) => ({ email: x.email, sub: x.keycloak_sub, recht: x.superadmin ? "project_admin" : "describe" }));
}

export class LakekeeperRechten {
  private token: { waarde: string; tot: number } | null = null;
  private vorige = "";

  constructor(
    private pool: pg.Pool,
    private inst: LakekeeperInstelling,
    /** Het id in Keycloak bij een e-mailadres, voor wie nog nooit in het portaal inlogde. */
    private zoekSub: (email: string) => Promise<string | null>,
    private doeFetch: Fetch = fetch,
  ) {}

  private async haalToken(): Promise<string> {
    if (this.token && this.token.tot > Date.now()) return this.token.waarde;
    const r = await this.doeFetch(this.inst.tokenUrl, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ grant_type: "client_credentials", client_id: this.inst.clientId, client_secret: this.inst.geheim, scope: "lakekeeper" }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!r.ok) throw new Error(`Keycloak geeft geen token voor ${this.inst.clientId} (${r.status})`);
    const j = (await r.json()) as { access_token: string; expires_in?: number };
    this.token = { waarde: j.access_token, tot: Date.now() + Math.max(10, (j.expires_in ?? 60) - 60) * 1000 };
    return j.access_token;
  }

  private async vraag<T>(methode: string, pad: string, lichaam?: unknown): Promise<T> {
    const r = await this.doeFetch(`${this.inst.url}/management/v1${pad}`, {
      method: methode,
      headers: { authorization: `Bearer ${await this.haalToken()}`, ...(lichaam !== undefined ? { "content-type": "application/json" } : {}) },
      body: lichaam !== undefined ? JSON.stringify(lichaam) : undefined,
      signal: AbortSignal.timeout(15_000),
    });
    if (r.status === 401) this.token = null;
    if (!r.ok) throw new Error(`Lakekeeper ${methode} ${pad}: ${r.status} ${(await r.text()).slice(0, 200)}`);
    const tekst = await r.text();
    return (tekst ? JSON.parse(tekst) : undefined) as T;
  }

  /**
   * Brengt Lakekeeper in lijn met het portaal. Geeft het aantal wijzigingen;
   * 0 zonder iets te vragen als er sinds de vorige keer niets veranderde.
   */
  async bijwerken(): Promise<number> {
    const nodig = await gewenst(this.pool);
    const gegeven = (await this.pool.query("SELECT gebruiker, recht FROM lakekeeper_toewijzingen")).rows as { gebruiker: string; recht: Recht }[];
    const handtekening = JSON.stringify([nodig, gegeven]);
    if (handtekening === this.vorige) return 0;

    // Het id in Keycloak: uit het portaal, anders bij Keycloak opgezocht.
    const doel = new Map<string, { email: string; recht: Recht }>();
    for (const n of nodig) {
      const sub = n.sub ?? await this.zoekSub(n.email).catch(() => null);
      if (sub) doel.set(`oidc~${sub}|${n.recht}`, { email: n.email, recht: n.recht });
    }
    const had = new Set(gegeven.map((g) => `${g.gebruiker}|${g.recht}`));
    const erbij = [...doel.keys()].filter((k) => !had.has(k));
    const eraf = gegeven.filter((g) => !doel.has(`${g.gebruiker}|${g.recht}`));
    if (!erbij.length && !eraf.length) {
      this.vorige = handtekening;
      return 0;
    }

    const bestaand = await this.vraag<{ assignments: { type: string; user?: string }[] }>("GET", "/permissions/project/assignments");
    const staat = new Set(bestaand.assignments.filter((a) => a.user).map((a) => `${a.user}|${a.type}`));
    let n = 0;
    for (const k of erbij) {
      const [gebruiker, recht] = k.split("|") as [string, Recht];
      const { email } = doel.get(k)!;
      // Lakekeeper kent een mens pas na zijn eerste inlog; het portaal meldt hem vast aan.
      await this.vraag("POST", "/user", { id: gebruiker, name: email, email, "user-type": "human", "update-if-exists": true });
      if (staat.has(k)) continue; // al gezet, door het installatiescript of met de hand: niet van het portaal
      await this.vraag("POST", "/permissions/project/assignments", { writes: [{ type: recht, user: gebruiker }] });
      await this.pool.query("INSERT INTO lakekeeper_toewijzingen (gebruiker, recht) VALUES ($1, $2) ON CONFLICT DO NOTHING", [gebruiker, recht]);
      n++;
    }
    for (const g of eraf) {
      if (staat.has(`${g.gebruiker}|${g.recht}`)) {
        await this.vraag("POST", "/permissions/project/assignments", { deletes: [{ type: g.recht, user: g.gebruiker }] });
      }
      await this.pool.query("DELETE FROM lakekeeper_toewijzingen WHERE gebruiker = $1 AND recht = $2", [g.gebruiker, g.recht]);
      n++;
    }
    // Wat er nu staat, is de nieuwe uitgangssituatie: zonder wijziging de volgende keer niets vragen.
    const nu = (await this.pool.query("SELECT gebruiker, recht FROM lakekeeper_toewijzingen")).rows;
    this.vorige = JSON.stringify([nodig, nu]);
    return n;
  }
}
