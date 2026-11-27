/**
 * Instellingen uit de omgeving. Het portaal start niet met een ontbrekend,
 * te kort of voorbeeldgeheim. Geen geheim komt ooit in een log, een URL of
 * de browser.
 */

export class ConfigFout extends Error {}

const VOORBEELDEN = /^(changeme|change-me|verander-?mij|voorbeeld|example|secret|geheim|password|wachtwoord|test|xxx+|\*+)$/i;

function nodig(env: NodeJS.ProcessEnv, naam: string): string {
  const w = env[naam];
  if (!w || !w.trim()) throw new ConfigFout(`${naam} ontbreekt`);
  return w.trim();
}

/** Een geheim: lang genoeg, geen voorbeeldwaarde, niet één teken herhaald. */
export function geheim(env: NodeJS.ProcessEnv, naam: string, minimaal: number): string {
  const w = nodig(env, naam);
  if (w.length < minimaal) throw new ConfigFout(`${naam} is te kort (minstens ${minimaal} tekens)`);
  if (VOORBEELDEN.test(w) || /^(.)\1+$/.test(w) || /voorbeeld|example|changeme|verander/i.test(w)) {
    throw new ConfigFout(`${naam} is een voorbeeldwaarde`);
  }
  if (new Set(w).size < 10) throw new ConfigFout(`${naam} is niet willekeurig genoeg`);
  return w;
}

export interface Config {
  /** De enige hostnaam waarop het portaal antwoordt, bijvoorbeeld admin.datafundament.haarlem.dev. */
  host: string;
  /** Het eigen adres, https://<host>; ook de verplichte Origin bij wijzigende verzoeken. */
  herkomst: string;
  poort: number;
  adminSecret: string;
  databaseUrl: string;
  hoofdaccountEmail: string;
  oidc: { issuer: string; clientId: string; clientSecret: string } | null;
  /**
   * Keycloak binnen het compose-netwerk (http://keycloak:8080), voor het beheer
   * van inlogaccounts met het service-account van dezelfde client. Null: het
   * portaal beheert geen inlogaccounts (geen knoppen voor uitnodiging en herstel).
   */
  keycloakIntern: string | null;
  /** Rechten van mensen in Lakekeeper (DF-ADR-020); null als LK_BEHEER_GEHEIM niet is gezet. */
  lakekeeperRechten: { tokenUrl: string; clientId: string; geheim: string } | null;
  smtp: { host: string; poort: number; gebruiker: string; wachtwoord: string; afzender: string; tls: "starttls" | "tls" | "geen" } | null;
  /**
   * De onderdelen van het platform, binnen het compose-netwerk. Het portaal
   * leest er de stand uit en start jobs in Dagster (verwijderverzoeken).
   */
  koppelingen: {
    dagster: string; dagsterLocatie: string; lakekeeper: string; trino: string; garage: string;
    /** OpenMetadata, de catalogus (DF-ADR-007); null als het er niet is. */
    openmetadata: string | null;
    /**
     * De kluis: OpenBao op dfw, dat de HMAC van een BSN berekent met de sleutel
     * kluis-bsn, dezelfde als bij de ingestie. Het portaal ziet de sleutel nooit en
     * bewaart het BSN nooit (DF-ADR-015).
     */
    kluis: { adres: string; token: string } | null;
  };
  /**
   * Waar het portaal de regels voor Trino schrijft (DF-ADR-017), en waar het
   * manifest van dbt staat (welke kolommen gevoelig zijn). Null: geen regels.
   */
  trinoRegels: { pad: string; manifest: string } | null;
  /** Waar het portaal de lijst schrijft van wie door de poort mag (DF-ADR-018); null: geen lijst. */
  poortPad: string | null;
  /**
   * Het token waarmee Trino zijn gebeurtenissen aflevert op de interne poort
   * (DF-ADR-016). Zonder token luistert de ontvanger niet.
   */
  datavragen: { token: string; poort: number } | null;
  /** Alleen voor tests en lokaal: een HMAC-sleutel in het proces in plaats van OpenBao. */
  kluisGeheim: string | null;
  /** Statische bestanden van de frontend. */
  frontendMap: string;
  /** Alleen voor tests en lokale ontwikkeling: e-mails naar een functie in plaats van SMTP. */
  vertrouwProxy: boolean;
}

export function leesConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const host = nodig(env, "BEHEER_HOST").toLowerCase();
  if (!/^[a-z0-9.-]+(:\d+)?$/.test(host)) throw new ConfigFout("BEHEER_HOST is geen hostnaam");
  const herkomst = env.BEHEER_HERKOMST?.trim() || `https://${host}`;
  const oidcAan = !!env.OIDC_ISSUER;
  const smtpAan = !!env.SMTP_HOST;
  return {
    host,
    herkomst,
    poort: Number(env.POORT ?? 4300),
    adminSecret: geheim(env, "ADMIN_SECRET", 32),
    databaseUrl: nodig(env, "DATABASE_URL"),
    hoofdaccountEmail: nodig(env, "HOOFDACCOUNT_EMAIL").toLowerCase(),
    keycloakIntern: oidcAan && env.KEYCLOAK_INTERN ? env.KEYCLOAK_INTERN.replace(/\/$/, "") : null,
    lakekeeperRechten: oidcAan && env.KEYCLOAK_INTERN && env.LK_BEHEER_GEHEIM
      ? {
          // Binnen het netwerk, zoals bij het beheer van Keycloak; de issuer in het token blijft het openbare adres.
          tokenUrl: `${env.KEYCLOAK_INTERN.replace(/\/$/, "")}${new URL(nodig(env, "OIDC_ISSUER")).pathname.replace(/\/$/, "")}/protocol/openid-connect/token`,
          clientId: env.LK_BEHEER_CLIENT ?? "df-lk-beheer",
          geheim: geheim(env, "LK_BEHEER_GEHEIM", 20),
        }
      : null,
    oidc: oidcAan
      ? { issuer: nodig(env, "OIDC_ISSUER").replace(/\/$/, ""), clientId: nodig(env, "OIDC_CLIENT_ID"), clientSecret: geheim(env, "OIDC_CLIENT_SECRET", 32) }
      : null,
    smtp: smtpAan
      ? {
          host: nodig(env, "SMTP_HOST"),
          poort: Number(env.SMTP_POORT ?? 587),
          gebruiker: env.SMTP_GEBRUIKER ?? "",
          wachtwoord: env.SMTP_GEBRUIKER ? geheim(env, "SMTP_WACHTWOORD", 8) : "",
          afzender: nodig(env, "SMTP_AFZENDER"),
          tls: (env.SMTP_TLS as "starttls" | "tls" | "geen") ?? "starttls",
        }
      : null,
    koppelingen: {
      dagster: (env.DAGSTER_URL ?? "http://dagster-webserver:3000").replace(/\/$/, ""),
      dagsterLocatie: env.DAGSTER_LOCATIE ?? "datafundament",
      lakekeeper: (env.LAKEKEEPER_URL ?? "http://lakekeeper:8181").replace(/\/$/, ""),
      trino: (env.TRINO_URL ?? "http://trino:8080").replace(/\/$/, ""),
      garage: (env.GARAGE_URL ?? "http://garage:3903").replace(/\/$/, ""),
      openmetadata: env.OPENMETADATA_URL ? env.OPENMETADATA_URL.replace(/\/$/, "") : null,
      kluis: env.KLUIS_BAO_ADRES
        ? { adres: env.KLUIS_BAO_ADRES.replace(/\/$/, ""), token: geheim(env, "KLUIS_BAO_TOKEN", 20) }
        : null,
    },
    trinoRegels: env.TRINO_REGELS_PAD
      ? { pad: env.TRINO_REGELS_PAD, manifest: env.DBT_MANIFEST ?? "/var/lib/dbt/laatste/manifest.json" }
      : null,
    poortPad: env.POORT_PAD ?? null,
    datavragen: env.DATAVRAGEN_TOKEN
      ? { token: geheim(env, "DATAVRAGEN_TOKEN", 32), poort: Number(env.DATAVRAGEN_POORT ?? 4301) }
      : null,
    kluisGeheim: env.KLUIS_GEHEIM ? geheim(env, "KLUIS_GEHEIM", 32) : null,
    frontendMap: env.FRONTEND_MAP ?? new URL("../../frontend/dist", import.meta.url).pathname,
    vertrouwProxy: env.VERTROUW_PROXY !== "nee",
  };
}
