import { bouwApp } from "./app.js";
import { leesConfig } from "./config.js";
import { maakPool } from "./db.js";
import { maakMailer } from "./mail.js";
import { Oidc } from "./oidc.js";
import { voerStatuswijzigingenUit } from "./persoon.js";
import { ruimPogingenOp } from "./pogingen.js";
import { routes } from "./routes/index.js";
import { dagelijks } from "./routes/audit.js";
import { ontvanger } from "./datavragen.js";
import { RegelSchrijver } from "./trinoregels.js";

const config = leesConfig();
const pool = maakPool(config.databaseUrl);
const oidc = config.oidc ? new Oidc(config.oidc, `${config.herkomst}/api/auth/terug`) : null;
const app = await bouwApp({ config, pool, oidc, mailer: maakMailer(config, (s) => console.log(s)) }, routes);
const d = app.diensten;
const regels = config.trinoRegels ? new RegelSchrijver(pool, config.trinoRegels.pad, config.trinoRegels.manifest, d.nu) : null;

// Elke 30 seconden: geplande statuswijzigingen, en pogingen ouder dan een dag weg.
const taken = async () => {
  try {
    await voerStatuswijzigingenUit(pool, d.nu());
    await ruimPogingenOp(d);
    await dagelijks(d);
    if (regels && await regels.schrijf()) app.log.info("regels voor Trino bijgewerkt");
  } catch (e) {
    app.log.error({ fout: (e as Error).message }, "periodieke taak mislukt");
  }
};
setInterval(taken, 30_000).unref();
await taken();

// Het token van de kluis is periodiek (768 uur): bij het starten en elke dag verlengen.
const verleng = () => d.koppelingen.verlengKluisToken().then((ok) => { if (config.koppelingen.kluis && !ok) app.log.warn("token van de kluis verlengen lukte niet"); });
verleng();
setInterval(verleng, 24 * 3600_000).unref();

await app.listen({ host: "0.0.0.0", port: config.poort });

// De ontvanger van Trino, op een eigen poort binnen het compose-netwerk (niet via Caddy).
const trino = config.datavragen ? ontvanger(pool, config.datavragen.token) : null;
if (trino && config.datavragen) await trino.listen({ host: "0.0.0.0", port: config.datavragen.poort });
for (const s of ["SIGTERM", "SIGINT"]) process.on(s, () => Promise.all([app.close(), trino?.close()]).then(() => pool.end()).finally(() => process.exit(0)));
