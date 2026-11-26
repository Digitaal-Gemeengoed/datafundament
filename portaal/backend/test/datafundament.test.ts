// Het Datafundament: platformstatus, dataproducten, toegangsaanvragen en verwijderverzoeken.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import type pg from "pg";
import type { FastifyInstance } from "fastify";
import { bouwApp } from "../src/app.ts";
import { routes } from "../src/routes/index.ts";
import { Koppelingen } from "../src/koppelingen.ts";
import { Sleutels, nieuwToken } from "../src/sleutels.ts";
import { geldigBsn } from "../src/kluis.ts";
import { verseDatabase, testConfig, kop, wijzig, GEHEIM } from "./hulp.ts";

const KLUIS = "q8Rz-3vNw!Yp6Lk1Tb9Mc4Hx7Jd2Gf5Sa0E";
let pool: pg.Pool, eigenaar: pg.Pool, app: FastifyInstance, appZonderKluis: FastifyInstance;
const klok = new Date("2026-11-27T10:00:00Z");
const sleutels = new Sleutels(GEHEIM);
const id: Record<string, string> = {};
const gestart: { verzoek: string; bsn_hmac: string }[] = [];
let runStatus = "STARTED";

/** Een nagebootst Dagster (GraphQL) en de gezondheidseinden van de onderdelen. */
const nepFetch: typeof fetch = async (invoer, init) => {
  const url = String(invoer);
  const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "content-type": "application/json" } });
  if (url.endsWith("/server_info")) return json({ dagster_version: "1.13.31" });
  if (url.endsWith("/health")) return url.includes("garage") ? new Response("", { status: 503 }) : new Response("ok");
  if (url.endsWith("/v1/info")) return json({ nodeVersion: { version: "484" }, starting: false });
  if (url.endsWith("/graphql")) {
    const { query, variables } = JSON.parse(String(init?.body));
    if (query.includes("runsOrError")) return json({ data: { runsOrError: { results: [{ runId: "r1", jobName: "ingestie", status: "SUCCESS", startTime: 1, endTime: 2 }] } } });
    if (query.includes("assetNodes")) {
      const a = (path: string[], groupName: string, t: number | null) => ({
        assetKey: { path }, groupName, description: `${path.join("/")}`, kinds: ["iceberg"], owners: [{ team: "data" }], dependencyKeys: [],
        assetMaterializations: t ? [{ timestamp: String(t), runId: "r1" }] : [],
      });
      return json({ data: { assetNodes: [
        a(["ruw_brp", "persoon"], "ruw_brp", klok.getTime() - 5 * 60_000),
        a(["ruw_belastingen", "aanslag"], "ruw_belastingen", klok.getTime() - 3 * 3600_000),
        a(["ruw_zaken", "zaken"], "ruw_zaken", null),
        a(["dataproduct", "testpersonen_per_buurt"], "dataproduct", klok.getTime()),
      ] } });
    }
    if (query.includes("launchRun")) {
      gestart.push(variables.p.runConfigData.ops.verwijder_persoon.config);
      return json({ data: { launchRun: { __typename: "LaunchRunSuccess", run: { runId: `run-${gestart.length}` } } } });
    }
    if (query.includes("logsForRun")) {
      return json({ data: { runOrError: { status: runStatus }, logsForRun: { events: [{ message: "gestart" }, { message: 'BEWIJS {"pseudoniem_vernietigd": true, "rijen_verwijderd": 12}' }] } } });
    }
  }
  return new Response("niet gevonden", { status: 404 });
};

async function sessie(account: string): Promise<string> {
  const token = nieuwToken();
  await pool.query("INSERT INTO sessies (account, token_hash, apparaat, ip, aangemaakt, laatst_actief, hard_einde) VALUES ($1, $2, 'test', '192.0.2.1', $3, $3, $4)", [
    account, sleutels.sessieHash(token), klok, new Date(klok.getTime() + 12 * 3600_000),
  ]);
  return `__Host-df_portaal=${token}`;
}

const vraag = (a: FastifyInstance, cookie: string, method: "GET" | "POST", url: string, payload?: object) =>
  a.inject({ method, url, headers: method === "GET" ? kop({ cookie }) : wijzig({ cookie }), payload: method === "GET" ? undefined : JSON.stringify(payload ?? {}) });

before(async () => {
  const d = await verseDatabase("df_portaal_t9");
  pool = d.pool;
  eigenaar = d.eigenaar;
  const config = testConfig("df_portaal_t9", { KLUIS_GEHEIM: KLUIS });
  app = await bouwApp({ config, pool, nu: () => klok, koppelingen: new Koppelingen(config.koppelingen, nepFetch) }, routes);
  appZonderKluis = await bouwApp({ config: d.config, pool, nu: () => klok, koppelingen: new Koppelingen(d.config.koppelingen, nepFetch) }, routes);
  const groep = async (naam: string, rechten: string[]) =>
    (await pool.query("INSERT INTO groepen (naam, rechten, niveau) VALUES ($1, $2, 2) RETURNING id", [naam, rechten])).rows[0].id;
  const engineers = await groep("Data-engineers", ["platform.view", "dataproducten.view", "toegang.aanvragen", "verwijderen.aanvragen"]);
  const privacy = await groep("Privacy", ["toegang.beoordelen", "verwijderen.aanvragen", "verwijderen.beoordelen", "dataproducten.view"]);
  const acc = async (email: string, groepen: string[]) => {
    const a = (await pool.query("INSERT INTO accounts (email, naam) VALUES ($1, $1) RETURNING id", [email])).rows[0].id;
    for (const g of groepen) await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [a, g]);
    return a;
  };
  id.eng = await acc("eng@test.nl", [engineers]);
  id.priv = await acc("priv@test.nl", [privacy]);
  id.priv2 = await acc("priv2@test.nl", [privacy]);
  id.geen = await acc("geen@test.nl", []);
});

after(async () => {
  await app.close();
  await appZonderKluis.close();
  await pool.end();
  await eigenaar.end();
});

test("elfproef voor het BSN", () => {
  assert.ok(geldigBsn("999993653"));
  assert.ok(!geldigBsn("999993654"));
  assert.ok(!geldigBsn("12345678"));
  assert.ok(!geldigBsn("000000000"));
});

test("platformstatus: onderdelen, runs en versheid per bron; alleen met platform.view", async () => {
  assert.equal((await vraag(app, await sessie(id.geen), "GET", "/api/platform")).statusCode, 403);
  const r = await vraag(app, await sessie(id.eng), "GET", "/api/platform");
  assert.equal(r.statusCode, 200);
  const j = r.json();
  assert.deepEqual(j.onderdelen.map((o: { naam: string; stand: string }) => `${o.naam}:${o.stand}`), ["Dagster:ok", "Lakekeeper:ok", "Trino:ok", "Garage:fout"]);
  assert.equal(j.runs[0].jobName, "ingestie");
  assert.deepEqual(j.versheid.map((v: { laag: string; stand: string }) => `${v.laag}:${v.stand}`), ["ruw_belastingen:verouderd", "ruw_brp:vers", "ruw_zaken:nooit"]);
});

test("dataproducten: alles uit Dagster, per laag", async () => {
  const j = (await vraag(app, await sessie(id.eng), "GET", "/api/dataproducten")).json();
  assert.deepEqual(j.map((a: { sleutel: string; laag: string }) => `${a.laag}:${a.sleutel}`), [
    "dataproduct:dataproduct/testpersonen_per_buurt", "ruw:ruw_belastingen/aanslag", "ruw:ruw_brp/persoon", "ruw:ruw_zaken/zaken",
  ]);
});

test("toegang: aanvragen, nooit je eigen aanvraag beoordelen, regels voor Trino", async () => {
  const eng = await sessie(id.eng);
  const fout = await vraag(app, eng, "POST", "/api/toegang", { dataproduct: "ruw", doel: "Analyse van buurten", grondslag: "taak van algemeen belang" });
  assert.equal(fout.statusCode, 400);
  const r = await vraag(app, eng, "POST", "/api/toegang", { dataproduct: "dataproduct/testpersonen_per_buurt", doel: "Analyse van buurten voor de wijkaanpak", grondslag: "taak van algemeen belang" });
  assert.equal(r.statusCode, 201);
  const aanvraag = r.json().id;
  // De aanvrager heeft het recht niet; en een beoordelaar die zelf aanvraagt, mag zijn eigen aanvraag niet beoordelen.
  assert.equal((await vraag(app, eng, "POST", `/api/toegang/${aanvraag}/beoordeling`, { besluit: "toegekend", toelichting: "prima" })).statusCode, 403);
  const priv = await sessie(id.priv);
  assert.equal((await vraag(app, priv, "POST", `/api/toegang/${aanvraag}/beoordeling`, { besluit: "toegekend", toelichting: "Doel past bij de grondslag" })).statusCode, 200);
  assert.equal((await vraag(app, priv, "POST", `/api/toegang/${aanvraag}/beoordeling`, { besluit: "afgewezen", toelichting: "toch niet" })).statusCode, 409);
  const regels = (await vraag(app, priv, "GET", "/api/toegang/regels")).json();
  assert.deepEqual(regels.tables[0], { user: "eng@test\\.nl", catalog: "lakehouse", schema: "dataproduct", table: "testpersonen_per_buurt", privileges: ["SELECT"] });
  // De eigen lijst van de aanvrager; intrekken door een beoordelaar.
  assert.equal((await vraag(app, eng, "GET", "/api/toegang")).json()[0].status, "toegekend");
  assert.equal((await vraag(app, priv, "POST", `/api/toegang/${aanvraag}/intrekken`, { toelichting: "Project afgerond" })).statusCode, 200);
  assert.equal((await vraag(app, priv, "GET", "/api/toegang/regels")).json().tables.length, 1);
  // De database bewaart alles: verwijderen kan niet, ook niet als eigenaar.
  await assert.rejects(eigenaar.query("DELETE FROM beheer.toegangsaanvragen"), /nooit verwijderd/);
});

test("verwijderverzoek: zonder kluis staat het uit", async () => {
  const r = await vraag(appZonderKluis, await sessie(id.eng), "POST", "/api/verwijderverzoeken", { bsn: "999993653", grondslag: "avg-art17", reden: "Verzoek van betrokkene, ontvangen per brief" });
  assert.equal(r.statusCode, 503);
});

test("verwijderverzoek: vier ogen, uitvoering in Dagster, bewijs; het BSN wordt nergens bewaard", async () => {
  const eng = await sessie(id.eng);
  assert.equal((await vraag(app, eng, "POST", "/api/verwijderverzoeken", { bsn: "999993654", grondslag: "avg-art17", reden: "Verzoek van betrokkene, per brief" })).statusCode, 400);
  const r = await vraag(app, eng, "POST", "/api/verwijderverzoeken", { bsn: "999993653", grondslag: "avg-art17", reden: "Verzoek van betrokkene, ontvangen per brief" });
  assert.equal(r.statusCode, 201);
  const verzoek = r.json().id;
  assert.equal((await vraag(app, eng, "POST", "/api/verwijderverzoeken", { bsn: "999993653", grondslag: "avg-art17", reden: "Nog een keer hetzelfde verzoek" })).statusCode, 409);

  // Het BSN staat nergens in de database, ook niet in de audit.
  const alles = (await eigenaar.query("SELECT (SELECT string_agg(t::text, ' ') FROM beheer.verwijderverzoeken t) || (SELECT string_agg(a::text, ' ') FROM beheer.audit a) AS x")).rows[0].x;
  assert.ok(!alles.includes("999993653"));

  // De aanvrager (zonder recht) en een beoordelaar die het zelf aanvroeg, mogen niet beoordelen.
  assert.equal((await vraag(app, eng, "POST", `/api/verwijderverzoeken/${verzoek}/beoordeling`, { besluit: "goedgekeurd", toelichting: "akkoord" })).statusCode, 403);
  const priv = await sessie(id.priv);
  const eigen = (await vraag(app, priv, "POST", "/api/verwijderverzoeken", { bsn: "999991772", grondslag: "bewaartermijn", reden: "Bewaartermijn jeugdhulp verlopen" })).json().id;
  assert.equal((await vraag(app, priv, "POST", `/api/verwijderverzoeken/${eigen}/beoordeling`, { besluit: "goedgekeurd", toelichting: "akkoord" })).statusCode, 403);

  const g = await vraag(app, priv, "POST", `/api/verwijderverzoeken/${verzoek}/beoordeling`, { besluit: "goedgekeurd", toelichting: "Verzoek is terecht, identiteit gecontroleerd" });
  assert.equal(g.statusCode, 200);
  assert.equal(g.json().status, "in-uitvoering");
  // Dagster kreeg alleen de HMAC, dezelfde als de ingestie maakt (ingestie/pseudoniem.py).
  const verwacht = createHmac("sha256", Buffer.from(KLUIS, "utf8")).update("bsn:999993653").digest("hex");
  assert.deepEqual(gestart.at(-1), { verzoek, bsn_hmac: verwacht });

  let lijst = (await vraag(app, priv, "GET", "/api/verwijderverzoeken")).json();
  assert.equal(lijst.verzoeken.find((v: { id: string }) => v.id === verzoek).status, "in-uitvoering");
  runStatus = "SUCCESS";
  lijst = (await vraag(app, eng, "GET", "/api/verwijderverzoeken")).json();
  const klaar = lijst.verzoeken.find((v: { id: string }) => v.id === verzoek);
  assert.equal(klaar.status, "uitgevoerd");
  assert.equal(klaar.bsn, "******653");
  assert.equal(klaar.bewijs.pseudoniem_vernietigd, true);
  assert.equal(klaar.bewijs.rijen_verwijderd, 12);
  await assert.rejects(eigenaar.query("UPDATE beheer.verwijderverzoeken SET status = 'aangevraagd', beoordeeld = NULL WHERE id = $1", [verzoek]), /afgerond/);
});
