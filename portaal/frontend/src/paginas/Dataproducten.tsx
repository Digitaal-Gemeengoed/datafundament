import { useState } from "react";
import {
  Alert, FormField, FormLabel, Heading1, Heading2, Paragraph,
  Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Textbox,
} from "@utrecht/component-library-react";
import { api, type Ik } from "../api";
import { t, tijd } from "../i18n";
import { L } from "../App";
import { relatief, useLaden } from "./gedeeld";

interface Asset {
  sleutel: string; groep: string; laag: string; omschrijving: string | null; soorten: string[];
  eigenaren: string[]; laatst: number | null; bovenstrooms: string[];
}
const LAGEN = ["dataproduct", "uniform", "ruw", "bron", "overig"] as const;

/** Alles wat het platform kent, per laag, met zoeken; vanaf hier toegang aanvragen. */
export function Dataproducten({ ik }: { ik: Ik }) {
  const { data, fout } = useLaden(() => api<Asset[]>("GET", "/api/dataproducten"));
  const [zoek, zetZoek] = useState("");
  const kanAanvragen = ik.rechten.includes("toegang.aanvragen");
  const z = zoek.trim().toLowerCase();
  const passend = (data ?? []).filter((a) => !z || a.sleutel.includes(z) || (a.omschrijving ?? "").toLowerCase().includes(z));
  return (
    <>
      <Heading1>{t("dataproducten")}</Heading1>
      <Paragraph className="ab-klein">{t("dataproductenUitleg")}</Paragraph>
      {fout && <Alert type="error"><Paragraph>{fout}</Paragraph></Alert>}
      <FormField label={<FormLabel htmlFor="d-zoek">{t("zoekenAsset")}</FormLabel>}>
        <Textbox id="d-zoek" value={zoek} maxLength={100} onChange={(e) => zetZoek(e.target.value)} />
      </FormField>
      {LAGEN.map((laag) => {
        const rijen = passend.filter((a) => a.laag === laag);
        if (!rijen.length) return null;
        return (
          <section key={laag}>
            <Heading2>{t(`laag_${laag}` as never)} <span className="ab-chip-n">{rijen.length}</span></Heading2>
            <div className="ab-tabel">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHeaderCell>{t("sleutel")}</TableHeaderCell>
                    <TableHeaderCell>{t("soort")}</TableHeaderCell>
                    <TableHeaderCell>{t("laatstBijgewerkt")}</TableHeaderCell>
                    <TableHeaderCell>{t("bovenstrooms")}</TableHeaderCell>
                    {laag === "dataproduct" && kanAanvragen && <TableHeaderCell><span className="ab-klein">{t("acties")}</span></TableHeaderCell>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rijen.map((a) => (
                    <TableRow key={a.sleutel}>
                      <TableCell>
                        <span className="ab-mono">{a.sleutel}</span>
                        {a.omschrijving && <div className="ab-klein">{a.omschrijving.split("\n")[0]}</div>}
                        {a.eigenaren.length > 0 && <div className="ab-klein">{t("eigenaar")}: {a.eigenaren.join(", ")}</div>}
                      </TableCell>
                      <TableCell>{a.soorten.join(", ") || "—"}</TableCell>
                      <TableCell title={a.laatst ? tijd(new Date(a.laatst).toISOString()) : undefined}>{a.laatst ? relatief(new Date(a.laatst).toISOString()) : t("nooit")}</TableCell>
                      <TableCell className="ab-klein ab-mono">{a.bovenstrooms.slice(0, 4).join(", ")}{a.bovenstrooms.length > 4 ? ` +${a.bovenstrooms.length - 4}` : ""}</TableCell>
                      {laag === "dataproduct" && kanAanvragen && (
                        <TableCell><L naar={`/toegang?dataproduct=${encodeURIComponent(a.sleutel)}`}>{t("toegangAanvragen")}</L></TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>
        );
      })}
    </>
  );
}
