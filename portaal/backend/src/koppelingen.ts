import { AppFout } from "./app.js";
import type { Config } from "./config.js";

export interface Onderdeel {
  naam: string;
  stand: "ok" | "fout";
  toelichting: string;
  ms: number;
}

export interface Run {
  runId: string;
  jobName: string;
  status: string;
  startTime: number | null;
  endTime: number | null;
}

export interface Asset {
  sleutel: string;
  groep: string;
  omschrijving: string | null;
  soorten: string[];
  eigenaren: string[];
  laatst: number | null;
  laatsteRun: string | null;
  bovenstrooms: string[];
}

/**
 * De onderdelen van het platform, over het interne netwerk. Het portaal leest
 * de stand (Dagster, Lakekeeper, Trino, Garage) en start in Dagster de job die
 * een verwijderverzoek uitvoert. Het portaal zelf raakt het lakehouse en de
 * kluis nooit aan (DF-ADR-015).
 */
export class Koppelingen {
  constructor(
    private readonly c: Config["koppelingen"],
    private readonly doeFetch: typeof fetch = fetch,
  ) {}

  private async haal(url: string, init: RequestInit = {}, ms = 4000): Promise<Response> {
    return this.doeFetch(url, { ...init, signal: AbortSignal.timeout(ms) });
  }

  /** Is elk onderdeel bereikbaar? Nooit een fout: een onderdeel dat niet antwoordt, staat op "fout". */
  async gezondheid(): Promise<Onderdeel[]> {
    const proeven: [string, string, (r: Response) => Promise<string>][] = [
      ["Dagster", `${this.c.dagster}/server_info`, async (r) => `versie ${(await r.json()).dagster_version ?? "?"}`],
      ["Lakekeeper", `${this.c.lakekeeper}/health`, async () => "catalogus antwoordt"],
      ["Trino", `${this.c.trino}/v1/info`, async (r) => {
        const j = await r.json();
        return j.starting ? "start nog op" : `versie ${j.nodeVersion?.version ?? "?"}`;
      }],
      ["Garage", `${this.c.garage}/health`, async () => "opslag antwoordt"],
    ];
    return Promise.all(proeven.map(async ([naam, url, uitleg]) => {
      const begin = Date.now();
      try {
        const r = await this.haal(url);
        if (!r.ok) return { naam, stand: "fout" as const, toelichting: `HTTP ${r.status}`, ms: Date.now() - begin };
        return { naam, stand: "ok" as const, toelichting: await uitleg(r), ms: Date.now() - begin };
      } catch (e) {
        return { naam, stand: "fout" as const, toelichting: (e as Error).name === "TimeoutError" ? "geen antwoord" : "niet bereikbaar", ms: Date.now() - begin };
      }
    }));
  }

  /** Een vraag aan Dagster (GraphQL). */
  async dagster<T>(query: string, variables: Record<string, unknown> = {}): Promise<T> {
    let r: Response;
    try {
      r = await this.haal(`${this.c.dagster}/graphql`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query, variables }),
      }, 15000);
    } catch {
      throw new AppFout(502, "dagster-onbereikbaar", "Dagster antwoordt niet.");
    }
    const j = (await r.json().catch(() => ({}))) as { data?: T; errors?: { message: string }[] };
    if (!r.ok || j.errors?.length || !j.data) throw new AppFout(502, "dagster-fout", "Dagster gaf een fout.", j.errors?.map((e) => e.message));
    return j.data;
  }

  async runs(limit = 25): Promise<Run[]> {
    const d = await this.dagster<{ runsOrError: { results?: Run[] } }>(
      `query ($limit: Int) { runsOrError(limit: $limit) { ... on Runs { results { runId jobName status startTime endTime } } } }`,
      { limit },
    );
    return d.runsOrError.results ?? [];
  }

  /** Alle assets: bronnen, ruwe lagen, uniforme laag en dataproducten, met de laatste materialisatie. */
  async assets(): Promise<Asset[]> {
    type Ruw = {
      assetKey: { path: string[] };
      groupName: string;
      description: string | null;
      kinds: string[];
      owners: { email?: string; team?: string }[];
      dependencyKeys: { path: string[] }[];
      assetMaterializations: { timestamp: string; runId: string }[];
    };
    const d = await this.dagster<{ assetNodes: Ruw[] }>(
      `query { assetNodes {
         assetKey { path } groupName description kinds
         owners { ... on UserAssetOwner { email } ... on TeamAssetOwner { team } }
         dependencyKeys { path }
         assetMaterializations(limit: 1) { timestamp runId }
       } }`,
    );
    return d.assetNodes.map((a) => ({
      sleutel: a.assetKey.path.join("/"),
      groep: a.groupName,
      omschrijving: a.description,
      soorten: a.kinds ?? [],
      eigenaren: (a.owners ?? []).map((o) => o.email ?? o.team ?? "").filter(Boolean),
      laatst: a.assetMaterializations[0] ? Number(a.assetMaterializations[0].timestamp) : null,
      laatsteRun: a.assetMaterializations[0]?.runId ?? null,
      bovenstrooms: a.dependencyKeys.map((k) => k.path.join("/")),
    })).sort((x, y) => x.sleutel.localeCompare(y.sleutel));
  }

  /** Start de job die een verwijderverzoek uitvoert. Geeft het run-id. */
  async startVerwijderen(verzoek: string, bsnHmac: string): Promise<string> {
    const d = await this.dagster<{ launchRun: { __typename: string; run?: { runId: string }; message?: string } }>(
      `mutation ($p: ExecutionParams!) { launchRun(executionParams: $p) {
         __typename
         ... on LaunchRunSuccess { run { runId } }
         ... on PythonError { message }
         ... on RunConfigValidationInvalid { pipelineName }
       } }`,
      {
        p: {
          selector: { repositoryLocationName: this.c.dagsterLocatie, repositoryName: "__repository__", jobName: "verwijderen" },
          runConfigData: { ops: { verwijder_persoon: { config: { verzoek, bsn_hmac: bsnHmac } } } },
        },
      },
    );
    if (d.launchRun.__typename !== "LaunchRunSuccess" || !d.launchRun.run) {
      throw new AppFout(502, "dagster-start-mislukt", "De job verwijderen kon niet starten.", d.launchRun.__typename);
    }
    return d.launchRun.run.runId;
  }

  /** De stand van een run, en het bewijs dat de job vastlegt (een logregel "BEWIJS {...}"). */
  async runStand(runId: string): Promise<{ status: string; bewijs: Record<string, unknown> | null }> {
    const d = await this.dagster<{ runOrError: { status?: string }; logsForRun: { events?: { message?: string }[] } }>(
      `query ($id: ID!) {
         runOrError(runId: $id) { ... on Run { status } }
         logsForRun(runId: $id) { ... on EventConnection { events { ... on MessageEvent { message } } } }
       }`,
      { id: runId },
    );
    const regel = (d.logsForRun.events ?? []).map((e) => e.message ?? "").find((m) => m.startsWith("BEWIJS "));
    let bewijs: Record<string, unknown> | null = null;
    if (regel) {
      try {
        bewijs = JSON.parse(regel.slice(7));
      } catch {
        bewijs = null;
      }
    }
    return { status: d.runOrError.status ?? "ONBEKEND", bewijs };
  }
}
