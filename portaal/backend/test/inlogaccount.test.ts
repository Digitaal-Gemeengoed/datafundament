// Inlogaccounts in Keycloak vanuit het portaal: uitnodiging opnieuw, wachtwoord en authenticator herstellen.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import type pg from "pg";
import type { FastifyInstance } from "fastify";
import { bouwApp } from "../src/app.ts";
import { routes } from "../src/routes/index.ts";
import { KeycloakBeheer, type Herstel } from "../src/keycloakbeheer.ts";
import { Sleutels, nieuwToken } from "../src/sleutels.ts";
import { verseDatabase, kop, wijzig, GEHEIM } from "./hulp.ts";

let pool: pg.Pool, eigenaar: pg.Pool, app: FastifyInstance;
const klok = new Date("2026-11-27T10:00:00Z");
const sleutels = new Sleutels(GEHEIM);
const id: Record<string, string> = {};

// Een nep-Keycloak: wie er is, en welke mails er gingen.
const gebruikers = new Map<string, { id: string; open: Herstel[]; otp: boolean }>();
const mails: { id: string; wat: Herstel[] }[] = [];
let mailFaalt = false;
const nepKeycloak = {
  async inlogaccount(email: string) {
    const g = gebruikers.get(email);
    return g ? { id: g.id, actief: true, openStappen: g.open, authenticator: g.otp } : null;
  },
  async zorgVoor(email: string) {
    const g = gebruikers.get(email);
    if (g) return { id: g.id, nieuw: false };
    gebruikers.set(email, { id: `kc-${email}`, open: ["wachtwoord", "authenticator"], otp: false });
    return { id: `kc-${email}`, nieuw: true };
  },
  async stuurMail(kid: string, wat: Herstel[]) {
    if (mailFaalt) throw Object.assign(new Error("Keycloak kon de mail niet versturen."), { status: 502, code: "mail-mislukt" });
    mails.push({ id: kid, wat });
  },
} as unknown as KeycloakBeheer;

async function sessie(account: string): Promise<string> {
  const token = nieuwToken();
  await pool.query("INSERT INTO sessies (account, token_hash, apparaat, ip, aangemaakt, laatst_actief, hard_einde) VALUES ($1, $2, 'test', '192.0.2.1', $3, $3, $4)",
    [account, sleutels.sessieHash(token), klok, new Date(klok.getTime() + 12 * 3600_000)]);
  return `__Host-df_portaal=${token}`;
}
const vraag = async (cookie: string, method: "GET" | "POST", url: string, body?: object) =>
  app.inject({ method, url, headers: method === "GET" ? kop({ cookie }) : wijzig({ cookie }), payload: method === "GET" ? undefined : JSON.stringify(body ?? {}) });

before(async () => {
  const d = await verseDatabase("df_portaal_t12");
  pool = d.pool;
  eigenaar = d.eigenaar;
  app = await bouwApp({ config: d.config, pool, nu: () => klok, keycloak: nepKeycloak }, routes);
  const g = (await pool.query("INSERT INTO groepen (naam, rechten, niveau) VALUES ('Beheer', '{accounts.view,accounts.manage,groups.view}', 3) RETURNING id")).rows[0].id;
  id.beh = (await pool.query("INSERT INTO accounts (email, naam) VALUES ('beh@test.nl', 'Beheerder') RETURNING id")).rows[0].id;
  await pool.query("INSERT INTO lidmaatschappen (account, groep) VALUES ($1, $2)", [id.beh, g]);
  id.oud = (await pool.query("INSERT INTO accounts (email, naam) VALUES ('oud@test.nl', 'Oude Gebruiker') RETURNING id")).rows[0].id;
  gebruikers.set("oud@test.nl", { id: "kc-oud", open: [], otp: true });
});

after(async () => {
  await app.close();
  await pool.end();
  await eigenaar.end();
});

test("een nieuw account: inlogaccount in Keycloak en de mail voor wachtwoord en authenticator", async () => {
  const c = await sessie(id.beh);
  const r = await vraag(c, "POST", "/api/accounts", { email: "Nieuw@Test.nl", naam: "Nieuwe Collega", taal: "nl", groepen: [], reden: "Nieuwe analist" });
  assert.equal(r.statusCode, 201, r.body);
  assert.equal(r.json().inlogmail, "verstuurd");
  assert.deepEqual(mails.at(-1), { id: "kc-nieuw@test.nl", wat: ["wachtwoord", "authenticator"] });
  const detail = (await vraag(c, "GET", `/api/accounts/${r.json().id}`)).json();
  assert.deepEqual(detail.inlog, { bestaat: true, actief: true, openStappen: ["wachtwoord", "authenticator"], authenticator: false });
});

test("opnieuw versturen en herstellen: alleen wat gevraagd is; een nieuw inlogaccount krijgt beide", async () => {
  const c = await sessie(id.beh);
  const r = await vraag(c, "POST", `/api/accounts/${id.oud}/inlogmail`, { wat: ["authenticator"], reden: "Telefoon kwijt, gebeld" });
  assert.equal(r.statusCode, 200);
  assert.deepEqual(mails.at(-1), { id: "kc-oud", wat: ["authenticator"] });
  gebruikers.delete("oud@test.nl");
  await vraag(c, "POST", `/api/accounts/${id.oud}/inlogmail`, { wat: ["wachtwoord"], reden: "Nog nooit ingelogd" });
  assert.deepEqual(mails.at(-1), { id: "kc-oud@test.nl", wat: ["wachtwoord", "authenticator"] });
  assert.equal((await vraag(c, "POST", `/api/accounts/${id.oud}/inlogmail`, { wat: [], reden: "niets gekozen" })).statusCode, 400);
  const audit = (await pool.query("SELECT details FROM audit WHERE actie = 'account.inlogmail' AND doel = $1 ORDER BY id", [id.oud])).rows;
  assert.equal(audit.length, 2);
  assert.equal(audit[0].details.reden, "Telefoon kwijt, gebeld");
});

test("geen recht, of de mail mislukt: een nette melding en een spoor in de audit", async () => {
  const zelf = await sessie(id.oud);
  assert.equal((await vraag(zelf, "POST", `/api/accounts/${id.beh}/inlogmail`, { wat: ["wachtwoord"], reden: "mag ik dit?" })).statusCode, 403);
  mailFaalt = true;
  const r = await vraag(await sessie(id.beh), "POST", `/api/accounts/${id.oud}/inlogmail`, { wat: ["wachtwoord"], reden: "Wachtwoord vergeten" });
  mailFaalt = false;
  assert.notEqual(r.statusCode, 200);
  assert.equal((await pool.query("SELECT count(*)::int AS n FROM audit WHERE actie = 'account.inlogmail' AND resultaat = 'fout'")).rows[0].n, 1);
});

test("KeycloakBeheer: intern adres, service-account, mail met verplichte stappen en een link van drie dagen", async () => {
  const verzoeken: { url: string; method: string; body?: string }[] = [];
  const nep = (async (url: string, init: RequestInit = {}) => {
    verzoeken.push({ url, method: init.method ?? "GET", body: init.body?.toString() });
    if (url.endsWith("/token")) return new Response(JSON.stringify({ access_token: "t", expires_in: 300 }));
    if (url.includes("/users?email=")) return new Response(JSON.stringify(verzoeken.filter((v) => v.method === "POST" && v.url.endsWith("/users")).length ? [{ id: "u1", username: "a@b.nl" }] : []));
    if (url.includes("/users?username=")) return new Response("[]");
    return new Response(null, { status: 204 });
  }) as typeof fetch;
  const k = new KeycloakBeheer("https://id.voorbeeld.nl/realms/datafundament", "df-portaal", "geheim", "http://keycloak:8080", nep);
  const r = await k.zorgVoor("a@b.nl", "Anna de Boer");
  assert.deepEqual(r, { id: "u1", nieuw: true });
  const maak = verzoeken.find((v) => v.method === "POST" && v.url.endsWith("/users"))!;
  assert.equal(maak.url, "http://keycloak:8080/admin/realms/datafundament/users");
  assert.deepEqual(JSON.parse(maak.body!).requiredActions, ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]);
  assert.equal(JSON.parse(maak.body!).firstName, "Anna de");
  await k.stuurMail("u1", ["authenticator"]);
  const mail = verzoeken.at(-1)!;
  assert.equal(mail.url, "http://keycloak:8080/admin/realms/datafundament/users/u1/execute-actions-email?lifespan=259200");
  assert.equal(mail.body, JSON.stringify(["CONFIGURE_TOTP"]));
  assert.equal(verzoeken[0].url, "http://keycloak:8080/realms/datafundament/protocol/openid-connect/token");
});
