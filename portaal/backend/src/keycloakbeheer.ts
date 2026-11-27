import { AppFout } from "./app.js";

/**
 * De inlogaccounts in Keycloak, via het service-account van de client
 * df-portaal (server/keycloak.sh: realm-management view-users en manage-users,
 * en de scope kc-admin-api). Naar het voorbeeld van oa-beheer.
 *
 * Wachtwoorden en authenticators zet het portaal nooit: Keycloak stuurt de
 * gebruiker een mail met een link (drie dagen geldig) om ze zelf in te stellen.
 */

/** Wat de gebruiker via de mail van Keycloak (opnieuw) instelt. */
export type Herstel = "wachtwoord" | "authenticator";
export const ACTIE: Record<Herstel, string> = { wachtwoord: "UPDATE_PASSWORD", authenticator: "CONFIGURE_TOTP" };
/** Zo lang is de link in de mail geldig: drie dagen. */
export const LINK_UREN = 72;

export interface Inlogaccount {
  id: string;
  actief: boolean;
  /** Wat de gebruiker nog moet instellen (de mail is nog niet gebruikt). */
  openStappen: Herstel[];
  /** Heeft een authenticator-app gekoppeld. */
  authenticator: boolean;
}

interface Gebruiker {
  id: string;
  username: string;
  email?: string;
  enabled?: boolean;
  requiredActions?: string[];
}

function stapVan(methode: string, pad: string): string {
  if (pad.includes("/execute-actions-email")) return "het laten versturen van de mail";
  if (pad.includes("/credentials")) return "het lezen van de inlogmiddelen";
  if (pad.startsWith("/users") && methode === "POST") return "het aanmaken van de gebruiker";
  if (pad.startsWith("/users") && methode === "GET") return "het lezen van de gebruikers";
  return "deze handeling";
}

export class KeycloakBeheer {
  private token: { waarde: string; tot: number } | null = null;
  private readonly realm: string;
  private readonly beheer: string;

  /**
   * `issuer` is het openbare adres van de realm (https://id.<domein>/realms/datafundament);
   * `intern` het adres binnen het compose-netwerk (http://keycloak:8080). Het
   * beheerscherm staat niet open naar buiten; het portaal gaat daarom intern.
   */
  constructor(
    issuer: string,
    private readonly clientId: string,
    private readonly geheim: string,
    intern?: string,
    private readonly doeFetch: typeof fetch = fetch,
  ) {
    const m = /^(.*)\/realms\/([^/]+)\/?$/.exec(issuer);
    const basis = (intern || m?.[1] || issuer).replace(/\/$/, "");
    const naam = m?.[2] ?? "datafundament";
    this.realm = `${basis}/realms/${naam}`;
    this.beheer = `${basis}/admin/realms/${naam}`;
  }

  private async haalToken(): Promise<string> {
    if (this.token && this.token.tot > Date.now()) return this.token.waarde;
    const r = await this.doeFetch(`${this.realm}/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ grant_type: "client_credentials", client_id: this.clientId, client_secret: this.geheim }),
      signal: AbortSignal.timeout(10_000),
    }).catch(() => null);
    if (!r?.ok) throw new AppFout(502, "keycloak-onbereikbaar", "Keycloak geeft het portaal geen toegang. Draai op dfc: sudo /opt/datafundament/server/installeer-platform.sh (dat zet het service-account van het portaal aan).");
    const j = (await r.json()) as { access_token: string; expires_in?: number };
    this.token = { waarde: j.access_token, tot: Date.now() + Math.max(10, (j.expires_in ?? 60) - 30) * 1000 };
    return j.access_token;
  }

  private async vraag<T>(methode: string, pad: string, lichaam?: unknown): Promise<T> {
    const r = await this.doeFetch(`${this.beheer}${pad}`, {
      method: methode,
      headers: { authorization: `Bearer ${await this.haalToken()}`, ...(lichaam !== undefined ? { "content-type": "application/json" } : {}) },
      body: lichaam !== undefined ? JSON.stringify(lichaam) : undefined,
      signal: AbortSignal.timeout(15_000),
    }).catch(() => null);
    if (!r) throw new AppFout(502, "keycloak-onbereikbaar", "Keycloak is nu niet bereikbaar.");
    if (r.status === 401 || r.status === 403) {
      this.token = null;
      throw new AppFout(502, "keycloak-geen-recht", `Keycloak weigert het portaal ${stapVan(methode, pad)}. Draai op dfc het installatiescript opnieuw; dat geeft het portaal de rechten.`);
    }
    if (r.status === 409) throw new AppFout(409, "keycloak-bestaat", "Keycloak kent al een gebruiker met dit e-mailadres.");
    if (r.status === 400 || r.status === 500) {
      const j = (await r.json().catch(() => ({}))) as { errorMessage?: string; error?: string };
      if (pad.includes("/execute-actions-email")) throw new AppFout(502, "mail-mislukt", "Keycloak kon de mail niet versturen. Is de mailserver ingesteld (SMTP_* in compose/.env, daarna het installatiescript)?");
      throw new AppFout(409, "keycloak-weigert", `Keycloak weigert dit: ${j.errorMessage ?? j.error ?? "ongeldige gegevens"}.`);
    }
    if (!r.ok) throw new AppFout(502, "keycloak-fout", `Keycloak gaf fout ${r.status}.`);
    const tekst = await r.text();
    return (tekst ? JSON.parse(tekst) : undefined) as T;
  }

  private async zoek(email: string): Promise<Gebruiker | null> {
    const e = encodeURIComponent(email);
    return (await this.vraag<Gebruiker[]>("GET", `/users?email=${e}&exact=true&briefRepresentation=false`))[0]
      ?? (await this.vraag<Gebruiker[]>("GET", `/users?username=${e}&exact=true&briefRepresentation=false`))[0]
      ?? null;
  }

  /** Het inlogaccount bij een e-mailadres; null als Keycloak het niet kent. */
  async inlogaccount(email: string): Promise<Inlogaccount | null> {
    const g = await this.zoek(email);
    if (!g) return null;
    const middelen = await this.vraag<{ type: string }[]>("GET", `/users/${encodeURIComponent(g.id)}/credentials`);
    return {
      id: g.id,
      actief: g.enabled !== false,
      openStappen: (Object.keys(ACTIE) as Herstel[]).filter((w) => (g.requiredActions ?? []).includes(ACTIE[w])),
      authenticator: middelen.some((m) => m.type === "otp"),
    };
  }

  /**
   * Zorgt dat er een inlogaccount is: gebruikersnaam is het e-mailadres, met de
   * verplichte stappen wachtwoord en authenticator. Geeft het id en of het nieuw is.
   */
  async zorgVoor(email: string, naam: string): Promise<{ id: string; nieuw: boolean }> {
    const er = await this.zoek(email);
    if (er) return { id: er.id, nieuw: false };
    const delen = naam.trim().split(/\s+/);
    await this.vraag("POST", "/users", {
      username: email, email, emailVerified: true, enabled: true,
      firstName: delen.length > 1 ? delen.slice(0, -1).join(" ") : naam.trim(),
      lastName: delen.length > 1 ? delen.at(-1) : "",
      requiredActions: [ACTIE.wachtwoord, ACTIE.authenticator],
    });
    const g = await this.zoek(email);
    if (!g) throw new AppFout(502, "keycloak-fout", "De gebruiker is aangemaakt, maar Keycloak geeft hem niet terug.");
    return { id: g.id, nieuw: true };
  }

  /**
   * Keycloak stuurt een mail met een link om dit (opnieuw) in te stellen. Een nieuwe
   * authenticator komt naast de oude; de gebruiker verwijdert de oude zelf in zijn
   * account (zoals bij 'Wachtwoord vergeten', zie server/keycloak.sh).
   */
  async stuurMail(id: string, wat: Herstel[], terug?: { clientId: string; adres: string }): Promise<void> {
    const q = new URLSearchParams({ lifespan: String(LINK_UREN * 3600) });
    if (terug) {
      q.set("client_id", terug.clientId);
      q.set("redirect_uri", terug.adres);
    }
    await this.vraag("PUT", `/users/${encodeURIComponent(id)}/execute-actions-email?${q}`, wat.map((w) => ACTIE[w]));
  }
}
