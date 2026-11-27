// Toegang voor een groep, en de rechten van mensen in Lakekeeper (DF-ADR-020).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import type pg from "pg";
import type { FastifyInstance } from "fastify";
import { bouwApp } from "../src/app.ts";
import { routes } from "../src/routes/index.ts";
import { Sleutels, nieuwToken } from "../src/sleutels.ts";
import { bouwRegels } from "../src/trinoregels.ts";
import { LakekeeperRechten } from "../src/lakekeeper.ts";
import { verseDatabase, kop, wijzig, GEHEIM } from "./hulp.ts";

let pool: pg.Pool, eigenaar: pg.Pool, app: FastifyInstance;
const klok = new Date("2026-11-27T10:00:00Z");
const sleutels = new Sleutels(GEHEIM);
const id: Record<string, string> = {};

async function sessie(account: string): Promise<string> {
  const token = nieuwToken();
  await pool.query("INSERT INTO sessies (account, token_hash, apparaat, ip, aangemaakt, laatst_actief, hard_einde) VALUES ($1, $2, 'test', '192.0.2.1', $3, $3, $4)", [
    account, sleutels.sessieHash(token), klok, new Date(klok.getTime() + 12 * 3600_000),
  ]);
  return `__Host-df_portaal=${token}`;
}
const vraag = (cookie: string, method: "GET" | "POST", url: string, payload?: object) =>
  app.inject({ method, url, headers: method === "GET" ? kop({ cookie }) : wijzig({ cookie }), payload: method === "GET" ? undefined : JSON.stringify(payload ?? {}) });
const lezers = async (dataproduct: string): Promise<string[]> => {
  const regels = (await bouwRegels(pool, klok, null)) as { tables: { user?: string; table?: string }[] };
  const tabel = dataproduct.split("/").at(-1)!;
  return regels.tables.filter((r) => r.table === tabel).map((r) => r.user!.replace(/^\^\(|\)\$$/g, "").replace(/\\/g, "")).sort();
};

before(async () => {
  const d = await verseDatabase("df_portaal_t20");
  pool = d.pool;
  eigenaar = d.eigenaar;
  app = await bouwApp({ config: d.config, pool, nu: () => klok }, routes);
  const groep = async (naam: string, rechten: string[], superadmin = false) =>
    (await pool.query("INSERT INTO groepen (naam, rechten, niveau, superadmin) VALUES ($1, $2, 2, $3) RETURNING id", [naam, rechten, superadmin])).rows[0].id;
  id.wonen = await groep("Team Wonen", ["toegang.aanvragen"]);
  id.privacy = await groep("Privacy", ["toegang.beoordelen"]);
  id.beheer = await groep("Platformbeheer", ["platform.bedienen"]);
  id.super = await groep("Superadmins", [], true);
  const acc = async (email: string, groepen: string[], sub: string | null = null) => {
    const a = (await pool.query("INSERT INTO accounts (email, naam, keycloak_sub) VALUES ($1, $1, $2) RETURNING id", [email, sub])).rows[0].id;
    for (const g of groepen) await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [a, g]);
    return a;
  };
  id.anna = await acc("anna@test.nl", [id.wonen]);
  id.bram = await acc("bram@test.nl", [id.wonen]);
  id.priv = await acc("priv@test.nl", [id.privacy]);
  id.privlid = await acc("privlid@test.nl", [id.privacy, id.wonen]);
  id.buiten = await acc("buiten@test.nl", [id.privacy]);
  id.kees = await acc("kees@test.nl", [id.beheer], "11111111-aaaa-bbbb-cccc-000000000001");
  id.sara = await acc("sara@test.nl", [id.super], "11111111-aaaa-bbbb-cccc-000000000002");
  id.nieuw = await acc("nieuw@test.nl", [id.beheer]); // nog nooit in het portaal ingelogd
});

after(async () => {
  await app.close();
  await pool.end();
  await eigenaar.end();
});

test("toegang voor een groep: alle leden, vier ogen buiten de groep, volgt het lidmaatschap", async () => {
  const anna = await sessie(id.anna);
  const aanvraag = { dataproduct: "dataproduct/woningen_per_buurt", doel: "Woningbouwopgave per buurt", grondslag: "taak van algemeen belang" };
  // Alleen voor een groep waar je lid van bent.
  assert.equal((await vraag(anna, "POST", "/api/toegang", { ...aanvraag, groep: id.privacy })).statusCode, 403);
  assert.deepEqual((await vraag(anna, "GET", "/api/toegang/groepen")).json().map((g: { naam: string; leden: number }) => `${g.naam}:${g.leden}`), ["Team Wonen:3"]);
  const r = await vraag(anna, "POST", "/api/toegang", { ...aanvraag, groep: id.wonen });
  assert.equal(r.statusCode, 201);
  const a = r.json().id;
  await assert.rejects(eigenaar.query("INSERT INTO beheer.toegangsaanvragen (dataproduct, aanvrager, doel, grondslag, groep, groep_naam) VALUES ('dataproduct/x', $1, 'iets om te doen', 'geen', $2, 'Privacy')", [id.anna, id.privacy]), /geen lid/);

  // Bram (lid) ziet de aanvraag ook; wie in de groep zit, beoordeelt niet.
  const bram = (await vraag(await sessie(id.bram), "GET", "/api/toegang")).json();
  assert.equal(bram[0].groep_naam, "Team Wonen");
  const privlid = await sessie(id.privlid);
  assert.equal((await vraag(privlid, "GET", "/api/toegang")).json().find((x: { id: string }) => x.id === a).mag_beoordelen, false);
  const fout = await vraag(privlid, "POST", `/api/toegang/${a}/beoordeling`, { besluit: "toegekend", toelichting: "prima zo" });
  assert.equal(fout.statusCode, 403);
  assert.equal(fout.json().fout, "eigen-groep");
  await assert.rejects(eigenaar.query("UPDATE beheer.toegangsaanvragen SET status = 'toegekend', beoordelaar = $2, beoordeeld = now(), toelichting = 'zelf' WHERE id = $1", [a, id.privlid]), /lid van de groep/);

  const ok = await vraag(await sessie(id.priv), "POST", `/api/toegang/${a}/beoordeling`, { besluit: "toegekend", toelichting: "Doel past bij de grondslag", met_persoonsgegevens: true });
  assert.equal(ok.statusCode, 200);
  assert.deepEqual(await lezers(aanvraag.dataproduct), ["anna@test.nl", "bram@test.nl", "privlid@test.nl"]);

  // Wie erbij komt, krijgt het; wie eruit gaat of geblokkeerd wordt, verliest het.
  await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [id.buiten, id.wonen]);
  await pool.query("DELETE FROM lidmaatschappen WHERE account = $1 AND groep = $2", [id.bram, id.wonen]);
  await pool.query("UPDATE accounts SET status = 'geblokkeerd' WHERE id = $1", [id.privlid]);
  assert.deepEqual(await lezers(aanvraag.dataproduct), ["anna@test.nl", "buiten@test.nl"]);

  // De groepen tonen welke data erbij hoort.
  const groepen = (await vraag(await sessie(id.sara), "GET", "/api/groepen")).json();
  assert.deepEqual(groepen.find((g: { naam: string }) => g.naam === "Team Wonen").dataproducten, ["dataproduct/woningen_per_buurt (met persoonsgegevens)"]);

  // De groep ligt vast; verdwijnt ze, dan geldt de toekenning voor niemand.
  await assert.rejects(eigenaar.query("UPDATE beheer.toegangsaanvragen SET groep = $2 WHERE id = $1", [a, id.privacy]), /ligt vast/);
  await eigenaar.query("DELETE FROM beheer.groepen WHERE id = $1", [id.wonen]);
  assert.deepEqual(await lezers(aanvraag.dataproduct), []);
  const lijst = (await vraag(await sessie(id.priv), "GET", "/api/toegang")).json();
  assert.equal(lijst.find((x: { id: string }) => x.id === a).groep_weg, true);
});

test("Lakekeeper: bedienen = describe, superadmin = project_admin; intrekken alleen wat het portaal gaf", async () => {
  const toewijzingen = new Set<string>(["oidc~11111111-aaaa-bbbb-cccc-000000000002|project_admin"]); // van het installatiescript
  const gebruikers: string[] = [];
  let vragen = 0;
  const nep: typeof fetch = async (invoer, init) => {
    const url = String(invoer);
    const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "content-type": "application/json" } });
    if (url.endsWith("/token")) {
      assert.match(String(init?.body), /client_id=df-lk-beheer/);
      return json({ access_token: "tok", expires_in: 3600 });
    }
    vragen++;
    assert.equal(new Headers(init?.headers).get("authorization"), "Bearer tok");
    if (url.endsWith("/management/v1/user")) {
      gebruikers.push(JSON.parse(String(init?.body)).id);
      return json({});
    }
    if (url.endsWith("/permissions/project/assignments")) {
      if (init?.method === "GET") return json({ assignments: [...toewijzingen].map((t) => ({ user: t.split("|")[0], type: t.split("|")[1] })) });
      const b = JSON.parse(String(init?.body));
      for (const w of b.writes ?? []) toewijzingen.add(`${w.user}|${w.type}`);
      for (const w of b.deletes ?? []) toewijzingen.delete(`${w.user}|${w.type}`);
      return new Response(null, { status: 204 });
    }
    return new Response("?", { status: 404 });
  };
  const lk = new LakekeeperRechten(pool, { url: "http://lakekeeper:8181", tokenUrl: "http://keycloak:8080/realms/datafundament/protocol/openid-connect/token", clientId: "df-lk-beheer", geheim: "x" },
    async (email) => (email === "nieuw@test.nl" ? "11111111-aaaa-bbbb-cccc-000000000003" : null), nep);

  assert.equal(await lk.bijwerken(), 2);
  assert.deepEqual([...toewijzingen].sort(), [
    "oidc~11111111-aaaa-bbbb-cccc-000000000001|describe",
    "oidc~11111111-aaaa-bbbb-cccc-000000000002|project_admin",
    "oidc~11111111-aaaa-bbbb-cccc-000000000003|describe",
  ]);
  assert.equal(gebruikers.length, 3);
  // Niets veranderd: geen enkele vraag aan Lakekeeper.
  vragen = 0;
  assert.equal(await lk.bijwerken(), 0);
  assert.equal(await lk.bijwerken(), 0);
  assert.equal(vragen, 0);

  // Kees verliest het recht, Sara wordt geblokkeerd: Kees gaat eruit; Sara's recht kwam van het installatiescript en blijft.
  await pool.query("DELETE FROM lidmaatschappen WHERE account = $1", [id.kees]);
  await pool.query("UPDATE accounts SET status = 'geblokkeerd' WHERE id = $1", [id.sara]);
  assert.equal(await lk.bijwerken(), 1);
  assert.deepEqual([...toewijzingen].sort(), [
    "oidc~11111111-aaaa-bbbb-cccc-000000000002|project_admin",
    "oidc~11111111-aaaa-bbbb-cccc-000000000003|describe",
  ]);
  assert.deepEqual((await pool.query("SELECT gebruiker, recht FROM lakekeeper_toewijzingen")).rows,
    [{ gebruiker: "oidc~11111111-aaaa-bbbb-cccc-000000000003", recht: "describe" }]);
});
