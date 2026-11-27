import type { ReactNode } from "react";
import { Heading1, Heading2, Paragraph, StatusBadge } from "@utrecht/component-library-react";
import { api, type Ik } from "../api";
import { t, tijd } from "../i18n";
import { L } from "../App";
import { actieTekst, relatief, useLaden } from "./gedeeld";

interface Overzicht {
  niveau: number;
  accounts?: { status: string; n: number }[];
  gepland?: number;
  eerstvolgend?: { id: string; status: string; ingang: string; account: string; naam: string }[];
  zonderGroep?: number;
  nooitIngelogd?: number;
  audit?: { vandaag: number; mislukt: number; nood_week: number };
  recent?: { id: number; tijd: string; email: string | null; actie: string; resultaat: string }[];
  actieveSessies?: number;
}

function groet(): string {
  const u = new Date().getHours();
  return t(u < 12 ? "goedemorgen" : u < 18 ? "goedemiddag" : "goedenavond");
}

/** Een getal met uitleg; met een adres is de hele kaart een link. */
function Getal({ getal, titel, naar, toon }: { getal: number | string; titel: string; naar?: string; toon?: "let-op" | "rustig" }) {
  const binnen = (
    <>
      <span className="ab-getal">{getal}</span>
      <span className="ab-getal-titel">{titel}</span>
    </>
  );
  const klasse = `ab-kaart ab-getalkaart${toon === "let-op" ? " let-op" : ""}`;
  return naar ? <L naar={naar} className={klasse}>{binnen}</L> : <div className={klasse}>{binnen}</div>;
}

function Blok({ titel, rechts, children }: { titel: string; rechts?: ReactNode; children: ReactNode }) {
  return (
    <section className="ab-kaart ab-blok">
      <header className="ab-blok-kop">
        <Heading2>{titel}</Heading2>
        {rechts}
      </header>
      {children}
    </section>
  );
}

/** Wat je ziet, hangt af van je niveau en je rechten. */
export function Dashboard({ ik }: { ik: Ik }) {
  const r = new Set(ik.rechten);
  const { data } = useLaden(() => api<Overzicht>("GET", "/api/dashboard"));
  const platform = useLaden(() => (r.has("platform.view") ? api<{ onderdelen: { naam: string; stand: string; toelichting: string }[]; versheid: { laag: string; stand: string; ritme?: string }[] }>("GET", "/api/platform") : Promise.resolve(null)));

  const n = (s: string) => data?.accounts?.find((a) => a.status === s)?.n ?? 0;
  const aandacht: { tekst: ReactNode; naar?: string; ernst: "let-op" | "info" }[] = [];
  const telling = (tekst: string, n: number) => <span className="ab-telling">{tekst}<span className="ab-chip-n">{n}</span></span>;
  if (data?.audit?.mislukt) aandacht.push({ tekst: telling(t("mislukteAanmeldingenAandacht"), data.audit.mislukt), naar: "/audit", ernst: "let-op" });
  if (data?.audit?.nood_week) aandacht.push({ tekst: telling(t("noodAandacht"), data.audit.nood_week), naar: "/audit", ernst: "let-op" });
  if (data?.zonderGroep) aandacht.push({ tekst: telling(t("zonderGroep"), data.zonderGroep), naar: "/accounts?groep=geen", ernst: "info" });
  if (data?.nooitIngelogd) aandacht.push({ tekst: telling(t("nooitIngelogd"), data.nooitIngelogd), naar: "/accounts?nooit=1", ernst: "info" });
  for (const w of data?.eerstvolgend ?? []) {
    aandacht.push({ tekst: <>{w.naam} {t("wordt")} <b>{t(w.status as "actief")}</b> {t("op")} {tijd(w.ingang)}</>, naar: `/accounts/${w.account}`, ernst: "info" });
  }
  for (const o of platform.data?.onderdelen ?? []) {
    if (o.stand !== "ok") aandacht.push({ tekst: <>{o.naam}: {o.toelichting}</>, naar: "/platform", ernst: "let-op" });
  }
  for (const v of platform.data?.versheid ?? []) {
    if (v.stand !== "vers") aandacht.push({ tekst: <>{v.laag}: {t(v.stand === "nooit" ? "nooitGeladen" : v.ritme === "nacht" ? "verouderdNacht" : "verouderd")}</>, naar: "/platform", ernst: "let-op" });
  }

  return (
    <>
      <div className="ab-welkom">
        <div>
          <Heading1>{groet()}, {ik.naam}</Heading1>
          <Paragraph className="ab-klein">{t("overzichtUitleg")}</Paragraph>
        </div>
      </div>

      <div className="ab-getallen">
        {data?.accounts && <Getal getal={n("actief")} titel={t("accountsActief")} naar="/accounts?status=actief" />}
        {data?.accounts && <Getal getal={n("geblokkeerd") + n("gedeactiveerd")} titel={t("accountsDicht")} naar="/accounts?status=dicht" />}
        {data?.gepland !== undefined && <Getal getal={data.gepland} titel={t("geplandeWijzigingen")} naar="/accounts/gepland" />}
        {data?.actieveSessies !== undefined && <Getal getal={data.actieveSessies} titel={t("actieveSessies")} naar="/accounts/sessies" />}
        {data?.audit && <Getal getal={data.audit.mislukt} titel={t("mislukteAanmeldingen")} naar="/audit" toon={data.audit.mislukt ? "let-op" : undefined} />}
        {data?.audit && <Getal getal={data.audit.nood_week} titel={t("noodtoegangWeek")} naar="/audit" toon={data.audit.nood_week ? "let-op" : undefined} />}
      </div>

      <div className="ab-twee">
        <div className="ab-kolom">
          {(data?.accounts || data?.audit) && (
            <Blok titel={t("aandacht")}>
              {aandacht.length === 0 ? (
                <Paragraph className="ab-leeg">✓ {t("niksAanDeHand")}</Paragraph>
              ) : (
                <ul className="ab-aandacht">
                  {aandacht.map((a, i) => (
                    <li key={i} className={a.ernst}>{a.naar ? <L naar={a.naar}>{a.tekst}</L> : a.tekst}</li>
                  ))}
                </ul>
              )}
            </Blok>
          )}
          {data?.recent && (
            <Blok titel={t("recenteActiviteit")} rechts={<L naar="/audit">{t("alleActiviteit")} →</L>}>
              <ul className="ab-activiteit">
                {data.recent.map((g) => (
                  <li key={g.id}>
                    <span className={`ab-stip${g.resultaat === "ok" || /^2\d\d$/.test(g.resultaat) ? "" : " fout"}`} aria-hidden="true" />
                    <span className="ab-activiteit-wat">
                      <span>{actieTekst(g.actie)}</span>
                      <span className="ab-klein">{g.email ?? "—"}</span>
                    </span>
                    <span className="ab-klein ab-rechts" title={tijd(g.tijd)}>{relatief(g.tijd)}</span>
                  </li>
                ))}
              </ul>
            </Blok>
          )}
        </div>
        <div className="ab-kolom">
          {platform.data && (
            <Blok titel={t("platform")} rechts={<L naar="/platform">{t("alleDetails")} →</L>}>
              <dl className="ab-feiten">
                {platform.data.onderdelen.map((o) => (
                  <div key={o.naam}><dt>{o.naam}</dt><dd><StatusBadge status={o.stand === "ok" ? "success" : "danger"}>{o.stand === "ok" ? t("werkt") : t("storing")}</StatusBadge> <span className="ab-klein">{o.toelichting}</span></dd></div>
                ))}
              </dl>
            </Blok>
          )}
          <Blok titel={t("snelkoppelingen")}>
            <ul className="ab-snel">
              {r.has("accounts.manage") && <li><L naar="/accounts/nieuw">+ {t("accountNieuw")}</L></li>}
              {r.has("accounts.view") && <li><L naar="/accounts">{t("accounts")}</L></li>}
              {(r.has("groups.view") || r.has("groups.manage")) && <li><L naar="/groepen">{t("groepen")}</L></li>}
              {r.has("dataproducten.view") && <li><L naar="/dataproducten">{t("dataproducten")}</L></li>}
              {r.has("toegang.aanvragen") && <li><L naar="/toegang">+ {t("toegangAanvragen")}</L></li>}
              {r.has("verwijderen.aanvragen") && <li><L naar="/verwijderen">+ {t("verwijderverzoekNieuw")}</L></li>}
              {r.has("audit.view") && <li><L naar="/audit">{t("audit")}</L></li>}
              <li><L naar="/profiel">{t("apparaten")}</L></li>
            </ul>
          </Blok>
        </div>
      </div>
    </>
  );
}
