// Elke datavraag vastleggen (DF-ADR-016): de ontvanger van Trino en de zoekpagina.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import type pg from "pg";
import type { FastifyInstance } from "fastify";
import { bouwApp } from "../src/app.ts";
import { routes } from "../src/routes/index.ts";
import { ontvanger, uitGebeurtenis } from "../src/datavragen.ts";
import { Sleutels, nieuwToken } from "../src/sleutels.ts";
import { verseDatabase, kop, GEHEIM } from "./hulp.ts";

const TOKEN = "trino-token-0123456789abcdefghijklmnopqrstuv";
let pool: pg.Pool, eigenaar: pg.Pool, app: FastifyInstance, ontv: FastifyInstance;
const klok = new Date("2026-11-27T10:00:00Z");
const sleutels = new Sleutels(GEHEIM);
const id: Record<string, string> = {};

/** Een QueryCompletedEvent zoals de HTTP event listener van Trino die stuurt (ingekort). */
const gebeurtenis = (queryId: string, user: string, fout = false) => ({
  metadata: {
    queryId, transactionId: "t1", query: "SELECT buurtnaam, testpersonen FROM lakehouse.dataproduct.testpersonen_per_buurt WHERE gemeentenaam = 'Haarlem'",
    queryState: fout ? "FAILED" : "FINISHED", uri: "http://trino:8080/v1/query/" + queryId,
    tables: [{ catalog: "lakehouse", schema: "dataproduct", table: "testpersonen_per_buurt", authorization: "beheer", filters: [],
      columns: [{ column: "buurtnaam" }, { column: "testpersonen" }, { column: "gemeentenaam" }], directlyReferenced: true }],
    routines: [],
  },
  statistics: { cpuTime: "PT0.12S", wallTime: "PT0.4S", totalBytes: 18234, totalRows: 412, outputRows: 37, outputBytes: 900, writtenRows: 0, completedSplits: 3 },
  context: { user, principal: null, source: "DBeaver 25.2", remoteClientAddress: "172.31.0.9", userAgent: "Trino JDBC Driver/484", queryType: "SELECT",
    catalog: "lakehouse", schema: "dataproduct", serverVersion: "484", environment: "datafundament" },
  ioMetadata: { inputs: [{ catalogName: "lakehouse", schema: "dataproduct", table: "testpersonen_per_buurt", columns: [{ column: "buurtnaam" }, { column: "testpersonen" }, { column: "gemeentenaam" }] }] },
  failureInfo: fout ? { errorCode: { code: 1, name: "SYNTAX_ERROR", type: "USER_ERROR" }, failureType: "io.trino.sql.parser.ParsingException", failureMessage: "line 1:8: mismatched input" } : null,
  warnings: [],
  createTime: "2026-11-27T09:59:58.100Z", executionStartTime: "2026-11-27T09:59:58.200Z", endTime: "2026-11-27T09:59:58.600Z",
});

async function sessie(account: string): Promise<string> {
  const token = nieuwToken();
  await pool.query("INSERT INTO sessies (account, token_hash, apparaat, ip, aangemaakt, laatst_actief, hard_einde) VALUES ($1, $2, 'test', '192.0.2.1', $3, $3, $4)",
    [account, sleutels.sessieHash(token), klok, new Date(klok.getTime() + 12 * 3600_000)]);
  return `__Host-df_portaal=${token}`;
}

before(async () => {
  const d = await verseDatabase("df_portaal_t10");
  pool = d.pool;
  eigenaar = d.eigenaar;
  app = await bouwApp({ config: d.config, pool, nu: () => klok }, routes);
  ontv = ontvanger(pool, TOKEN);
  const g = (await pool.query("INSERT INTO groepen (naam, rechten, niveau) VALUES ('Privacy', '{datavragen.view}', 2) RETURNING id")).rows[0].id;
  id.priv = (await pool.query("INSERT INTO accounts (email, naam) VALUES ('priv@test.nl', 'Privacy') RETURNING id")).rows[0].id;
  await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [id.priv, g]);
  id.geen = (await pool.query("INSERT INTO accounts (email, naam) VALUES ('geen@test.nl', 'Geen') RETURNING id")).rows[0].id;
});

after(async () => {
  await app.close();
  await ontv.close();
  await pool.end();
  await eigenaar.end();
});

test("een gebeurtenis van Trino: wie, welke tabel en kolommen, hoeveel", () => {
  const v = uitGebeurtenis(gebeurtenis("20261127_095958_00001_abcde", "fabien"))!;
  assert.equal(v.gebruiker, "fabien");
  assert.equal(v.bron, "DBeaver 25.2");
  assert.equal(v.status, "FINISHED");
  assert.equal(v.rijen, 37);
  assert.deepEqual(v.tabellen, [{ tabel: "lakehouse.dataproduct.testpersonen_per_buurt", kolommen: ["buurtnaam", "gemeentenaam", "testpersonen"] }]);
  assert.equal(uitGebeurtenis({ metadata: { queryId: "x" } }), null); // een query-created-gebeurtenis: geen statistiek
});

test("de ontvanger: alleen met het token, elke query één keer, en niets is te wijzigen", async () => {
  const stuur = (body: object, token = TOKEN) =>
    ontv.inject({ method: "POST", url: "/trino/gebeurtenis", headers: { "content-type": "application/json", "x-datavragen-token": token }, payload: JSON.stringify(body) });
  assert.equal((await stuur(gebeurtenis("q1", "fabien"), "fout-token-0123456789abcdefghijklmnopqrstuv")).statusCode, 401);
  assert.equal((await stuur(gebeurtenis("q1", "fabien"))).statusCode, 204);
  assert.equal((await stuur(gebeurtenis("q1", "fabien"))).statusCode, 204); // opnieuw verstuurd door Trino: niet dubbel
  assert.equal((await stuur(gebeurtenis("q2", "erik", true))).statusCode, 204);
  assert.equal((await pool.query("SELECT count(*)::int AS n FROM datavragen")).rows[0].n, 2);
  await assert.rejects(eigenaar.query("UPDATE beheer.datavragen SET gebruiker = 'iemand anders'"), /niet gewijzigd/);
  await assert.rejects(eigenaar.query("DELETE FROM beheer.datavragen"), /niet gewijzigd/);
  await assert.rejects(eigenaar.query("TRUNCATE beheer.datavragen"), /niet gewijzigd/);
});

test("zoeken: alleen met datavragen.view; op gebruiker, tabel en status", async () => {
  const geen = await sessie(id.geen);
  assert.equal((await app.inject({ method: "GET", url: "/api/datavragen", headers: kop({ cookie: geen }) })).statusCode, 403);
  const priv = await sessie(id.priv);
  const haal = async (q = "") => (await app.inject({ method: "GET", url: `/api/datavragen${q}`, headers: kop({ cookie: priv }) })).json();
  const alles = await haal();
  assert.equal(alles.stand.totaal, 2);
  assert.equal(alles.stand.gebruikers, 2);
  assert.deepEqual((await haal("?gebruiker=fab")).vragen.map((v: { query_id: string }) => v.query_id), ["q1"]);
  assert.equal((await haal("?tabel=dataproduct.testpersonen")).vragen.length, 2);
  assert.equal((await haal("?tabel=uniform.persoon")).vragen.length, 0);
  const mislukt = (await haal("?status=FAILED")).vragen;
  assert.equal(mislukt[0].fout, "line 1:8: mismatched input");
  const een = (await app.inject({ method: "GET", url: `/api/datavragen/${mislukt[0].id}`, headers: kop({ cookie: priv }) })).json();
  assert.match(een.sql, /gemeentenaam = 'Haarlem'/);
});
