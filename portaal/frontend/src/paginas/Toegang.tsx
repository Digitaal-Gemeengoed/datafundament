import { useState, type FormEvent } from "react";
import {
  Checkbox, FormField, FormLabel, Heading1, Heading2, Paragraph, PrimaryActionButton, SecondaryActionButton, StatusBadge,
  Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Textarea, Textbox,
} from "@utrecht/component-library-react";
import { api, type Ik } from "../api";
import { t, tijd } from "../i18n";
import { foutTekst, MeldingVak, useLaden, type Melding } from "./gedeeld";

interface Aanvraag {
  id: string; dataproduct: string; doel: string; grondslag: string; gewenst_tot: string | null; status: string;
  toelichting: string | null; met_persoonsgegevens: boolean; aangemaakt: string; beoordeeld: string | null; aanvrager: string; aanvrager_email: string;
  beoordelaar: string | null; eigen: boolean; mag_beoordelen: boolean;
}
const KLEUR: Record<string, "success" | "danger" | "warning" | "neutral"> = { toegekend: "success", afgewezen: "danger", ingetrokken: "neutral", aangevraagd: "warning" };

/** Toegang tot een dataproduct aanvragen, beoordelen (vier ogen) en intrekken. */
export function Toegang({ ik }: { ik: Ik }) {
  const lijst = useLaden(() => api<Aanvraag[]>("GET", "/api/toegang"));
  const [m, zetM] = useState<Melding>(null);
  const beoordelaar = ik.rechten.includes("toegang.beoordelen");
  return (
    <>
      <Heading1>{t("toegangData")}</Heading1>
      <Paragraph className="ab-klein">{t("toegangUitleg")}</Paragraph>
      <MeldingVak m={m ?? (lijst.fout ? { soort: "fout", tekst: lijst.fout } : null)} />
      {ik.rechten.includes("toegang.aanvragen") && <Nieuw klaar={(x) => { zetM(x); lijst.herlaad(); }} />}
      <Heading2>{beoordelaar ? t("toegangData") : t("toegangAanvragen")}</Heading2>
      <div className="ab-tabel">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>{t("dataproduct")}</TableHeaderCell>
              <TableHeaderCell>{t("aanvrager")}</TableHeaderCell>
              <TableHeaderCell>{t("doel")}</TableHeaderCell>
              <TableHeaderCell>{t("status")}</TableHeaderCell>
              <TableHeaderCell><span className="ab-klein">{t("acties")}</span></TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(lijst.data ?? []).map((a) => (
              <TableRow key={a.id}>
                <TableCell><span className="ab-mono">{a.dataproduct}</span><div className="ab-klein">{tijd(a.aangemaakt)}{a.gewenst_tot ? ` · ${t("gewenstTot")}: ${a.gewenst_tot.slice(0, 10)}` : ""}</div></TableCell>
                <TableCell>{a.aanvrager}<div className="ab-klein">{a.aanvrager_email}</div></TableCell>
                <TableCell>{a.doel}<div className="ab-klein">{t("grondslag")}: {a.grondslag}</div></TableCell>
                <TableCell>
                  <StatusBadge status={KLEUR[a.status] ?? "neutral"}>{t(`st_${a.status}` as never)}</StatusBadge>
                  {a.status === "toegekend" && <div className="ab-klein">{t(a.met_persoonsgegevens ? "metPersoonsgegevensKort" : "gemaskeerdKort")}</div>}
                  {a.beoordelaar && <div className="ab-klein">{a.beoordelaar}</div>}
                  {a.toelichting && <div className="ab-klein">{a.toelichting}</div>}
                </TableCell>
                <TableCell><Acties a={a} beoordelaar={beoordelaar} klaar={(x) => { zetM(x); lijst.herlaad(); }} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {beoordelaar && <Regels />}
    </>
  );
}

function Nieuw({ klaar }: { klaar: (m: Melding) => void }) {
  const [v, zet] = useState({ dataproduct: new URLSearchParams(location.search).get("dataproduct") ?? "", doel: "", grondslag: "", gewenst_tot: "" });
  const [bezig, zetBezig] = useState(false);
  const stuur = async (e: FormEvent) => {
    e.preventDefault();
    zetBezig(true);
    try {
      await api("POST", "/api/toegang", { dataproduct: v.dataproduct, doel: v.doel, grondslag: v.grondslag, ...(v.gewenst_tot ? { gewenst_tot: v.gewenst_tot } : {}) });
      zet({ dataproduct: "", doel: "", grondslag: "", gewenst_tot: "" });
      klaar({ soort: "ok", tekst: t("st_aangevraagd") });
    } catch (x) {
      klaar({ soort: "fout", tekst: foutTekst(x) });
    } finally {
      zetBezig(false);
    }
  };
  return (
    <form className="ab-kaart ab-formulier" onSubmit={stuur}>
      <Heading2>{t("toegangAanvragen")}</Heading2>
      <FormField label={<FormLabel htmlFor="t-dp">{t("dataproduct")}</FormLabel>} description="dataproduct/… of dwh/dataproduct/…">
        <Textbox id="t-dp" value={v.dataproduct} required maxLength={200} pattern="^[a-z0-9_]+(/[a-z0-9_]+){1,3}$" onChange={(e) => zet({ ...v, dataproduct: e.target.value })} />
      </FormField>
      <FormField label={<FormLabel htmlFor="t-doel">{t("doel")}</FormLabel>} description={t("doelUitleg")}>
        <Textarea id="t-doel" value={v.doel} rows={2} required minLength={10} maxLength={2000} onChange={(e) => zet({ ...v, doel: e.target.value })} />
      </FormField>
      <FormField label={<FormLabel htmlFor="t-gr">{t("grondslag")}</FormLabel>} description={t("grondslagUitleg")}>
        <Textbox id="t-gr" value={v.grondslag} required minLength={3} maxLength={500} onChange={(e) => zet({ ...v, grondslag: e.target.value })} />
      </FormField>
      <FormField label={<FormLabel htmlFor="t-tot">{t("gewenstTot")}</FormLabel>}>
        <Textbox id="t-tot" type="date" value={v.gewenst_tot} onChange={(e) => zet({ ...v, gewenst_tot: e.target.value })} />
      </FormField>
      <PrimaryActionButton type="submit" disabled={bezig}>{t("aanvragen")}</PrimaryActionButton>
    </form>
  );
}

function Acties({ a, beoordelaar, klaar }: { a: Aanvraag; beoordelaar: boolean; klaar: (m: Melding) => void }) {
  const [open, zetOpen] = useState<null | "toegekend" | "afgewezen" | "intrekken">(null);
  const [toel, zetToel] = useState("");
  const [met, zetMet] = useState(false);
  const kanIntrekken = (a.eigen && a.status === "aangevraagd") || (beoordelaar && !a.eigen && a.status === "toegekend");
  if (!a.mag_beoordelen && !kanIntrekken) return <>{a.eigen && a.status === "aangevraagd" ? <span className="ab-klein">{t("vierOgen")}</span> : "—"}</>;
  const doe = async () => {
    try {
      if (open === "intrekken") await api("POST", `/api/toegang/${a.id}/intrekken`, { toelichting: toel });
      else await api("POST", `/api/toegang/${a.id}/beoordeling`, { besluit: open, toelichting: toel, ...(open === "toegekend" ? { met_persoonsgegevens: met } : {}) });
      klaar({ soort: "ok", tekst: t(open === "intrekken" ? "st_ingetrokken" : `st_${open}` as never) });
    } catch (x) {
      klaar({ soort: "fout", tekst: foutTekst(x) });
    }
  };
  if (open) {
    return (
      <div className="ab-formulier">
        <FormField label={<FormLabel htmlFor={`a-${a.id}`}>{t("toelichting")}</FormLabel>} description={t("toelichtingUitleg")}>
          <Textarea id={`a-${a.id}`} rows={2} value={toel} minLength={5} maxLength={2000} onChange={(e) => zetToel(e.target.value)} />
        </FormField>
        {open === "toegekend" && (
          <FormField type="checkbox" label={<FormLabel htmlFor={`p-${a.id}`} type="checkbox">{t("metPersoonsgegevens")}</FormLabel>} description={t("metPersoonsgegevensUitleg")}
            input={<Checkbox id={`p-${a.id}`} checked={met} onChange={(e) => zetMet(e.target.checked)} />} />
        )}
        <div className="ab-knoppen">
          <PrimaryActionButton onClick={doe} disabled={toel.trim().length < 5}>{t(open === "toegekend" ? "toekennen" : open === "afgewezen" ? "afwijzen" : "intrekken")}</PrimaryActionButton>
          <SecondaryActionButton onClick={() => zetOpen(null)}>{t("annuleren")}</SecondaryActionButton>
        </div>
      </div>
    );
  }
  return (
    <div className="ab-knoppen">
      {a.mag_beoordelen && a.status === "aangevraagd" && <SecondaryActionButton onClick={() => zetOpen("toegekend")}>{t("toekennen")}</SecondaryActionButton>}
      {a.mag_beoordelen && a.status === "aangevraagd" && <SecondaryActionButton onClick={() => zetOpen("afgewezen")}>{t("afwijzen")}</SecondaryActionButton>}
      {kanIntrekken && <SecondaryActionButton onClick={() => zetOpen("intrekken")}>{t("intrekken")}</SecondaryActionButton>}
    </div>
  );
}

function Regels() {
  const [regels, zet] = useState<string | null>(null);
  return (
    <section>
      <Heading2>{t("regelsTrino")}</Heading2>
      <Paragraph className="ab-klein">{t("regelsUitleg")}</Paragraph>
      {!regels && <SecondaryActionButton onClick={async () => zet(JSON.stringify(await api("GET", "/api/toegang/regels"), null, 2))}>{t("regelsTrino")}</SecondaryActionButton>}
      {regels && <pre className="ab-mono ab-kaart">{regels}</pre>}
    </section>
  );
}
