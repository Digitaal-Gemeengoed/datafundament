import {
  Alert, Heading1, Heading2, Paragraph, SecondaryActionButton, StatusBadge,
  Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow,
} from "@utrecht/component-library-react";
import { api } from "../api";
import { t, tijd } from "../i18n";
import { relatief, useLaden } from "./gedeeld";

interface Stand {
  onderdelen: { naam: string; stand: "ok" | "fout"; toelichting: string; ms: number }[];
  runs: { runId: string; jobName: string; status: string; startTime: number | null; endTime: number | null }[] | null;
  versheid: { laag: string; laatst: number | null; tabellen: number; stand: "vers" | "verouderd" | "nooit"; ritme?: "vijf-minuten" | "nacht" }[];
}

const RUN: Record<string, "success" | "danger" | "warning" | "neutral"> = { SUCCESS: "success", FAILURE: "danger", CANCELED: "warning", STARTED: "neutral", QUEUED: "neutral" };
const iso = (s: number | null) => (s ? new Date(s * 1000).toISOString() : null);

/** De stand van het platform: onderdelen, versheid per bron, laatste runs. */
export function Platform() {
  const { data, fout, herlaad } = useLaden(() => api<Stand>("GET", "/api/platform"));
  return (
    <>
      <Heading1>{t("platform")}</Heading1>
      {fout && <Alert type="error"><Paragraph>{fout}</Paragraph></Alert>}
      <SecondaryActionButton onClick={herlaad}>{t("verversen")}</SecondaryActionButton>
      {data && (
        <>
          <Heading2>{t("onderdelen")}</Heading2>
          <Paragraph className="ab-klein">{t("onderdelenUitleg")}</Paragraph>
          <div className="ab-getallen">
            {data.onderdelen.map((o) => (
              <div key={o.naam} className={`ab-kaart ab-getalkaart${o.stand === "ok" ? "" : " let-op"}`}>
                <span className="ab-getal-titel">{o.naam}</span>
                <StatusBadge status={o.stand === "ok" ? "success" : "danger"}>{o.stand === "ok" ? t("werkt") : t("storing")}</StatusBadge>
                <span className="ab-klein">{o.toelichting} · {o.ms} ms</span>
              </div>
            ))}
          </div>

          <Heading2>{t("versheid")}</Heading2>
          <Paragraph className="ab-klein">{t("versheidUitleg")}</Paragraph>
          {data.runs === null && <Alert type="warning"><Paragraph>{t("dagsterOnbereikbaar")}</Paragraph></Alert>}
          <div className="ab-tabel">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>{t("laag")}</TableHeaderCell>
                  <TableHeaderCell>{t("tabellen")}</TableHeaderCell>
                  <TableHeaderCell>{t("laatstBijgewerkt")}</TableHeaderCell>
                  <TableHeaderCell>{t("status")}</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.versheid.map((v) => (
                  <TableRow key={v.laag}>
                    <TableCell className="ab-mono">{v.laag}</TableCell>
                    <TableCell>{v.tabellen}</TableCell>
                    <TableCell title={v.laatst ? tijd(new Date(v.laatst).toISOString()) : undefined}>{v.laatst ? relatief(new Date(v.laatst).toISOString()) : t("nooit")}</TableCell>
                    <TableCell><StatusBadge status={v.stand === "vers" ? "success" : "warning"}>{t(v.stand === "vers" ? "vers" : v.stand === "nooit" ? "nooitGeladen" : v.ritme === "nacht" ? "verouderdNacht" : "verouderd")}</StatusBadge>
                      {v.ritme === "nacht" && <div className="ab-klein">{t("ritmeNacht")}</div>}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {data.runs && (
            <>
              <Heading2>{t("runs")}</Heading2>
              <div className="ab-tabel">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHeaderCell>{t("job")}</TableHeaderCell>
                      <TableHeaderCell>{t("gestart")}</TableHeaderCell>
                      <TableHeaderCell>{t("duur")}</TableHeaderCell>
                      <TableHeaderCell>{t("status")}</TableHeaderCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.runs.map((r) => (
                      <TableRow key={r.runId}>
                        <TableCell className="ab-mono">{r.jobName}</TableCell>
                        <TableCell>{tijd(iso(r.startTime))}</TableCell>
                        <TableCell>{r.startTime && r.endTime ? `${Math.round(r.endTime - r.startTime)} s` : "—"}</TableCell>
                        <TableCell><StatusBadge status={RUN[r.status] ?? "neutral"}>{r.status.toLowerCase()}</StatusBadge></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
