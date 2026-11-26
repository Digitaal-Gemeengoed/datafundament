import { useState, type FormEvent } from "react";
import {
  Alert, FormField, FormLabel, Heading1, Heading2, Paragraph, PrimaryActionButton, SecondaryActionButton, Select, SelectOption,
  StatusBadge, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Textarea, Textbox,
} from "@utrecht/component-library-react";
import { api, type Ik } from "../api";
import { t, tijd } from "../i18n";
import { foutTekst, MeldingVak, useLaden, type Melding } from "./gedeeld";

interface Verzoek {
  id: string; bsn: string; grondslag: string; reden: string; status: string; aangemaakt: string; beoordeeld: string | null;
  toelichting: string | null; dagster_run: string | null; afgerond: string | null; bewijs: Record<string, unknown> | null;
  aanvrager: string; beoordelaar: string | null; mag_beoordelen: boolean;
}
const KLEUR: Record<string, "success" | "danger" | "warning" | "neutral"> = {
  aangevraagd: "warning", "in-uitvoering": "neutral", uitgevoerd: "success", afgewezen: "neutral", mislukt: "danger",
};
const GRONDSLAGEN = ["avg-art17", "bewaartermijn", "onrechtmatig", "overig"];

/** Verwijderverzoeken: indienen, beoordelen door een tweede persoon, uitvoering en bewijs (DF-ADR-015). */
export function Verwijderen({ ik }: { ik: Ik }) {
  const lijst = useLaden(() => api<{ aan: boolean; verzoeken: Verzoek[] }>("GET", "/api/verwijderverzoeken"));
  const [m, zetM] = useState<Melding>(null);
  const klaar = (x: Melding) => { zetM(x); lijst.herlaad(); };
  return (
    <>
      <Heading1>{t("verwijderverzoeken")}</Heading1>
      <Paragraph className="ab-klein">{t("verwijderenUitleg")}</Paragraph>
      <MeldingVak m={m ?? (lijst.fout ? { soort: "fout", tekst: lijst.fout } : null)} />
      {lijst.data && !lijst.data.aan && <Alert type="warning"><Paragraph>{t("verwijderenUit")}</Paragraph></Alert>}
      {lijst.data?.aan && ik.rechten.includes("verwijderen.aanvragen") && <Nieuw klaar={klaar} />}
      <SecondaryActionButton onClick={lijst.herlaad}>{t("verversen")}</SecondaryActionButton>
      <div className="ab-tabel">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>{t("bsn")}</TableHeaderCell>
              <TableHeaderCell>{t("grondslag")}</TableHeaderCell>
              <TableHeaderCell>{t("aanvrager")}</TableHeaderCell>
              <TableHeaderCell>{t("status")}</TableHeaderCell>
              <TableHeaderCell><span className="ab-klein">{t("acties")}</span></TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(lijst.data?.verzoeken ?? []).map((v) => (
              <TableRow key={v.id}>
                <TableCell className="ab-mono">{v.bsn}<div className="ab-klein">{tijd(v.aangemaakt)}</div></TableCell>
                <TableCell>{t(`gr_${v.grondslag.replace("-", "_")}` as never)}<div className="ab-klein">{v.reden}</div></TableCell>
                <TableCell>{v.aanvrager}{v.beoordelaar && <div className="ab-klein">{t("beoordelaar")}: {v.beoordelaar}</div>}</TableCell>
                <TableCell>
                  <StatusBadge status={KLEUR[v.status] ?? "neutral"}>{t(`st_${v.status}` as never)}</StatusBadge>
                  {v.toelichting && <div className="ab-klein">{v.toelichting}</div>}
                  {v.bewijs && <details><summary className="ab-klein">{t("bewijs")}</summary><pre className="ab-mono ab-klein">{JSON.stringify(v.bewijs, null, 2)}</pre></details>}
                  {v.afgerond && <div className="ab-klein">{tijd(v.afgerond)}</div>}
                </TableCell>
                <TableCell><Acties v={v} klaar={klaar} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}

function Nieuw({ klaar }: { klaar: (m: Melding) => void }) {
  const [v, zet] = useState({ bsn: "", grondslag: "avg-art17", reden: "" });
  const stuur = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api("POST", "/api/verwijderverzoeken", v);
      zet({ bsn: "", grondslag: "avg-art17", reden: "" });
      klaar({ soort: "ok", tekst: t("st_aangevraagd") });
    } catch (x) {
      klaar({ soort: "fout", tekst: foutTekst(x) });
    }
  };
  return (
    <form className="ab-kaart ab-formulier" onSubmit={stuur} autoComplete="off">
      <Heading2>{t("verwijderverzoekNieuw")}</Heading2>
      <FormField label={<FormLabel htmlFor="v-bsn">{t("bsn")}</FormLabel>} description={t("bsnUitleg")}>
        <Textbox id="v-bsn" value={v.bsn} required inputMode="numeric" pattern="[0-9]{9}" maxLength={9} onChange={(e) => zet({ ...v, bsn: e.target.value.replace(/\D/g, "") })} />
      </FormField>
      <FormField label={<FormLabel htmlFor="v-gr">{t("grondslag")}</FormLabel>}>
        <Select id="v-gr" value={v.grondslag} onChange={(e) => zet({ ...v, grondslag: e.target.value })}>
          {GRONDSLAGEN.map((g) => <SelectOption key={g} value={g}>{t(`gr_${g.replace("-", "_")}` as never)}</SelectOption>)}
        </Select>
      </FormField>
      <FormField label={<FormLabel htmlFor="v-reden">{t("reden")}</FormLabel>} description={t("redenVerwijderen")}>
        <Textarea id="v-reden" value={v.reden} rows={2} required minLength={10} maxLength={2000} onChange={(e) => zet({ ...v, reden: e.target.value })} />
      </FormField>
      <PrimaryActionButton type="submit">{t("indienen")}</PrimaryActionButton>
    </form>
  );
}

function Acties({ v, klaar }: { v: Verzoek; klaar: (m: Melding) => void }) {
  const [open, zetOpen] = useState<null | "goedgekeurd" | "afgewezen">(null);
  const [toel, zetToel] = useState("");
  if (!v.mag_beoordelen) return <>{v.status === "aangevraagd" ? <span className="ab-klein">{t("vierOgen")}</span> : "—"}</>;
  if (v.status === "mislukt") {
    return <SecondaryActionButton onClick={async () => {
      try { await api("POST", `/api/verwijderverzoeken/${v.id}/opnieuw`); klaar({ soort: "ok", tekst: t("st_in-uitvoering") }); } catch (x) { klaar({ soort: "fout", tekst: foutTekst(x) }); }
    }}>{t("opnieuw")}</SecondaryActionButton>;
  }
  if (v.status !== "aangevraagd") return <>—</>;
  if (open) {
    return (
      <div className="ab-formulier">
        <FormField label={<FormLabel htmlFor={`b-${v.id}`}>{t("toelichting")}</FormLabel>} description={t("toelichtingUitleg")}>
          <Textarea id={`b-${v.id}`} rows={2} value={toel} minLength={5} maxLength={2000} onChange={(e) => zetToel(e.target.value)} />
        </FormField>
        <div className="ab-knoppen">
          <PrimaryActionButton disabled={toel.trim().length < 5} onClick={async () => {
            try {
              const r = await api<{ status: string }>("POST", `/api/verwijderverzoeken/${v.id}/beoordeling`, { besluit: open, toelichting: toel });
              klaar({ soort: "ok", tekst: t(`st_${r.status}` as never) });
            } catch (x) {
              klaar({ soort: "fout", tekst: foutTekst(x) });
            }
          }}>{t(open === "goedgekeurd" ? "goedkeuren" : "afwijzen")}</PrimaryActionButton>
          <SecondaryActionButton onClick={() => zetOpen(null)}>{t("annuleren")}</SecondaryActionButton>
        </div>
      </div>
    );
  }
  return (
    <div className="ab-knoppen">
      <SecondaryActionButton onClick={() => zetOpen("goedgekeurd")}>{t("goedkeuren")}</SecondaryActionButton>
      <SecondaryActionButton onClick={() => zetOpen("afgewezen")}>{t("afwijzen")}</SecondaryActionButton>
    </div>
  );
}
