// De regels voor Trino (DF-ADR-017): wie wat mag lezen, en welke kolommen gemaskeerd zijn.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type pg from "pg";
import { RegelSchrijver, bouwRegels, uitManifest } from "../src/trinoregels.ts";
import { verseDatabase } from "./hulp.ts";

let pool: pg.Pool, eigenaar: pg.Pool;
const nu = new Date("2026-11-27T10:00:00Z");
const MANIFEST = {
  nodes: {
    "model.df.testpersonen_per_buurt": {
      resource_type: "model", name: "testpersonen_per_buurt", schema: "dataproduct", config: { schema: "dataproduct", database: "lakehouse" },
      columns: { buurtnaam: { name: "buurtnaam", meta: {} }, testpersonen: { name: "testpersonen" } },
    },
    "model.df.inwoners_per_adres": {
      resource_type: "model", name: "inwoners_per_adres", schema: "dataproduct", config: { schema: "dataproduct", database: "dwh" },
      columns: { postcode: { name: "postcode", meta: { privacy: "persoonsgegeven" } }, geboortejaar: { name: "geboortejaar", config: { meta: { privacy: "persoonsgegeven" } } },
                 wmo: { name: "wmo", meta: { privacy: "bijzonder" } }, aantal: { name: "aantal" } },
    },
    "test.df.iets": { resource_type: "test", name: "iets" },
  },
};

before(async () => {
  const d = await verseDatabase("df_portaal_t11");
  pool = d.pool;
  eigenaar = d.eigenaar;
  const g = async (naam: string, rechten: string[]) => (await pool.query("INSERT INTO groepen (naam, rechten, niveau) VALUES ($1, $2, 1) RETURNING id", [naam, rechten])).rows[0].id;
  const a = async (email: string, status = "actief") => (await pool.query("INSERT INTO accounts (email, naam, status) VALUES ($1, $1, $2) RETURNING id", [email, status])).rows[0].id;
  const eng = await g("Data-engineers", ["lagen.lezen"]);
  const ana = await g("Analisten", ["toegang.aanvragen"]);
  const de = await a("de@test.nl");
  await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [de, eng]);
  const weg = await a("weg@test.nl", "geblokkeerd");
  await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [weg, eng]);
  const an = await a("an+x@test.nl");
  await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [an, ana]);
  const beoordelaar = await a("priv@test.nl");
  const toekennen = async (dataproduct: string, met: boolean, tot: string | null = null) =>
    pool.query(`INSERT INTO toegangsaanvragen (dataproduct, aanvrager, doel, grondslag, gewenst_tot, status, beoordelaar, beoordeeld, toelichting, met_persoonsgegevens)
                VALUES ($1, $2, 'Analyse voor de wijkaanpak', 'taak van algemeen belang', $3, 'toegekend', $4, now(), 'akkoord', $5)`, [dataproduct, an, tot, beoordelaar, met]);
  await toekennen("dataproduct/testpersonen_per_buurt", false);
  await toekennen("dwh/dataproduct/inwoners_per_adres", false);
  await toekennen("dataproduct/verlopen", true, "2026-11-01");
  await toekennen("dataproduct/onbekend", false);
});

after(async () => {
  await pool.end();
  await eigenaar.end();
});

test("uit het manifest: per dataproduct de kolommen met een label", () => {
  const t = uitManifest(MANIFEST);
  assert.deepEqual(t.get("dataproduct/testpersonen_per_buurt")?.gevoelig, []);
  assert.deepEqual(t.get("dwh/dataproduct/inwoners_per_adres"),
    { catalog: "dwh", schema: "dataproduct", table: "inwoners_per_adres", gevoelig: ["geboortejaar", "postcode", "wmo"] });
});

test("regels: data-engineers alles; een toekenning gemaskeerd; verlopen, geblokkeerd en onbekend niets", async () => {
  const r = await bouwRegels(pool, nu, uitManifest(MANIFEST)) as { tables: Record<string, unknown>[] };
  assert.equal(r.tables[1].user, "^(openmetadata|de@test\\.nl)$");
  const van = r.tables.filter((t) => t.user === "^(an\\+x@test\\.nl)$");
  assert.deepEqual(van.map((t) => t.table), ["testpersonen_per_buurt", "inwoners_per_adres"]);
  assert.equal(van[0].columns, undefined);
  assert.deepEqual(van[1].columns, [{ name: "geboortejaar", mask: "NULL" }, { name: "postcode", mask: "NULL" }, { name: "wmo", mask: "NULL" }]);
  assert.equal(van[1].catalog, "dwh");
  assert.deepEqual(r.tables.at(-1), { privileges: [] });

  // Zonder manifest is niet bekend wat gevoelig is: alleen toekenningen met persoonsgegevens.
  const zonder = await bouwRegels(pool, nu, null) as { tables: Record<string, unknown>[] };
  assert.equal(zonder.tables.filter((t) => String(t.user ?? "").includes("an")).length, 0);
});

test("de schrijver schrijft alleen als er iets veranderde", async () => {
  const map = await mkdtemp(join(tmpdir(), "regels-"));
  await writeFile(join(map, "manifest.json"), JSON.stringify(MANIFEST));
  const s = new RegelSchrijver(pool, join(map, "rules.json"), join(map, "manifest.json"), () => nu);
  assert.equal(await s.schrijf(), true);
  assert.equal(await s.schrijf(), false);
  const regels = JSON.parse(await readFile(join(map, "rules.json"), "utf8"));
  assert.ok(regels.tables.some((t: { columns?: unknown[] }) => t.columns?.length === 3));
});

test("de poort: platform.bedienen of superadmin, alleen actieve accounts, nooit het hoofdaccount", async () => {
  const { bouwLijst, PoortSchrijver } = await import("../src/poort.ts");
  const g = (await pool.query("INSERT INTO groepen (naam, rechten, niveau) VALUES ('Platformbeheer', '{platform.bedienen}', 1) RETURNING id")).rows[0].id;
  const s = (await pool.query("INSERT INTO groepen (naam, rechten, niveau, superadmin) VALUES ('Super', '{}', 4, true) RETURNING id")).rows[0].id;
  for (const [email, groep, status] of [["ops@test.nl", g, "actief"], ["super@test.nl", s, "actief"], ["oudops@test.nl", g, "gedeactiveerd"]]) {
    const a = (await pool.query("INSERT INTO accounts (email, naam, status) VALUES ($1, $1, $2) RETURNING id", [email, status])).rows[0].id;
    await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [a, groep]);
  }
  assert.deepEqual(await bouwLijst(pool), ["ops@test.nl", "super@test.nl"]);
  const map = await mkdtemp(join(tmpdir(), "poort-"));
  const w = new PoortSchrijver(pool, join(map, "toegestaan.txt"));
  assert.equal(await w.schrijf(), true);
  assert.equal(await w.schrijf(), false);
  assert.equal(await readFile(join(map, "toegestaan.txt"), "utf8"), "ops@test.nl\nsuper@test.nl\n");
});
