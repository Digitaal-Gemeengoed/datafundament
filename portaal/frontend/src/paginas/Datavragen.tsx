import { useState } from "react";
import {
  Alert, FormField, FormLabel, Heading1, Paragraph, SecondaryActionButton, Select, SelectOption, StatusBadge,
  Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Textbox,
} from "@utrecht/component-library-react";
import { api } from "../api";
import { t, tijd } from "../i18n";
import { useLaden } from "./gedeeld";

interface Vraag {
  id: string; query_id: string; gebruiker: string; bron: string | null; client_adres: string | null; soort: string | null;
  status: string; fout: string | null; sql: string; tabellen: { tabel: string; kolommen: string[] }[];
  rijen: number | null; begin: string | null; einde: string | null;
}
interface Antwoord { stand: { totaal: number; vandaag: number; gebruikers: number }; vragen: Vraag[]; meer: string | null }

/** Elke datavraag aan Trino, te doorzoeken op wie, welke tabel en wanneer (DF-ADR-016). */
export function Datavragen() {
  const [f, zetF] = useState({ gebruiker: "", tabel: "", van: "", tot: "", status: "" });
  const [zoek, zetZoek] = useState(f);
  const qs = new URLSearchParams(Object.entries(zoek).filter(([, v]) => v)).toString();
  const { data, fout } = useLaden(() => api<Antwoord>("GET", `/api/datavragen${qs ? `?${qs}` : ""}`), [qs]);
  const [open, zetOpen] = useState<Record<string, string>>({});
  const toon = async (v: Vraag) => {
    if (open[v.id]) return zetOpen({ ...open, [v.id]: "" });
    const heel = await api<{ sql: string }>("GET", `/api/datavragen/${v.id}`);
    zetOpen({ ...open, [v.id]: heel.sql });
  };
  return (
    <>
      <Heading1>{t("datavragen")}</Heading1>
      <Paragraph className="ab-klein">{t("datavragenUitleg")}</Paragraph>
      {fout && <Alert type="error"><Paragraph>{fout}</Paragraph></Alert>}
      {data && (
        <div className="ab-getallen">
          <div className="ab-kaart ab-getalkaart"><span className="ab-getal-titel">{t("totaal")}</span><span className="ab-getal">{data.stand.totaal}</span></div>
          <div className="ab-kaart ab-getalkaart"><span className="ab-getal-titel">{t("laatste24uur")}</span><span className="ab-getal">{data.stand.vandaag}</span></div>
          <div className="ab-kaart ab-getalkaart"><span className="ab-getal-titel">{t("gebruikers")}</span><span className="ab-getal">{data.stand.gebruikers}</span></div>
        </div>
      )}
      <form className="ab-filters" onSubmit={(e) => { e.preventDefault(); zetZoek(f); }}>
        <FormField label={<FormLabel htmlFor="dv-g">{t("gebruiker")}</FormLabel>}><Textbox id="dv-g" value={f.gebruiker} maxLength={200} onChange={(e) => zetF({ ...f, gebruiker: e.target.value })} /></FormField>
        <FormField label={<FormLabel htmlFor="dv-t">{t("tabel")}</FormLabel>}><Textbox id="dv-t" value={f.tabel} placeholder="dataproduct.testpersonen_per_buurt" maxLength={300} onChange={(e) => zetF({ ...f, tabel: e.target.value.toLowerCase() })} /></FormField>
        <FormField label={<FormLabel htmlFor="dv-van">{t("van")}</FormLabel>}><Textbox id="dv-van" type="date" value={f.van} onChange={(e) => zetF({ ...f, van: e.target.value })} /></FormField>
        <FormField label={<FormLabel htmlFor="dv-tot">{t("tot")}</FormLabel>}><Textbox id="dv-tot" type="date" value={f.tot} onChange={(e) => zetF({ ...f, tot: e.target.value })} /></FormField>
        <FormField label={<FormLabel htmlFor="dv-s">{t("status")}</FormLabel>}>
          <Select id="dv-s" value={f.status} onChange={(e) => zetF({ ...f, status: e.target.value })}>
            <SelectOption value="">{t("alle")}</SelectOption>
            <SelectOption value="FINISHED">{t("gelukt")}</SelectOption>
            <SelectOption value="FAILED">{t("mislukte")}</SelectOption>
          </Select>
        </FormField>
        <SecondaryActionButton type="submit">{t("zoekenAsset")}</SecondaryActionButton>
      </form>
      <div className="ab-tabel">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>{t("tijdstip")}</TableHeaderCell>
              <TableHeaderCell>{t("gebruiker")}</TableHeaderCell>
              <TableHeaderCell>{t("tabellen")}</TableHeaderCell>
              <TableHeaderCell>{t("vraag")}</TableHeaderCell>
              <TableHeaderCell>{t("status")}</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.vragen ?? []).map((v) => (
              <TableRow key={v.id}>
                <TableCell>{tijd(v.einde)}</TableCell>
                <TableCell>{v.gebruiker}<div className="ab-klein">{v.bron ?? ""}{v.client_adres ? ` · ${v.client_adres}` : ""}</div></TableCell>
                <TableCell className="ab-klein">
                  {v.tabellen.length ? v.tabellen.map((x) => <div key={x.tabel}><span className="ab-mono">{x.tabel}</span>{x.kolommen.length > 0 && <> ({x.kolommen.join(", ")})</>}</div>) : "—"}
                </TableCell>
                <TableCell>
                  <pre className="ab-mono ab-klein ab-sql">{open[v.id] || v.sql}</pre>
                  <SecondaryActionButton onClick={() => toon(v)}>{open[v.id] ? t("minder") : t("helemaal")}</SecondaryActionButton>
                </TableCell>
                <TableCell>
                  <StatusBadge status={v.status === "FINISHED" ? "success" : "danger"}>{v.status === "FINISHED" ? t("gelukt") : t("mislukte")}</StatusBadge>
                  {v.rijen !== null && v.status === "FINISHED" && <div className="ab-klein">{v.rijen} {t("rijen")}</div>}
                  {v.fout && <div className="ab-klein">{v.fout}</div>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
