import { createHmac } from "node:crypto";

/** Elfproef voor een BSN (9 cijfers). */
export function geldigBsn(bsn: string): boolean {
  if (!/^[0-9]{9}$/.test(bsn)) return false;
  const som = [...bsn.slice(0, 8)].reduce((s, c, i) => s + Number(c) * (9 - i), 0) - Number(bsn[8]);
  return som % 11 === 0 && bsn !== "000000000";
}

/**
 * De HMAC van een BSN met de sleutel van de kluis, zoals de ingestie die maakt
 * (ingestie/pseudoniem.py). Met deze waarde vindt de job verwijderen het
 * pseudoniem; het BSN zelf verlaat het portaal niet.
 */
export function bsnHmac(bsn: string, kluisGeheim: string): Buffer {
  return createHmac("sha256", Buffer.from(kluisGeheim, "utf8")).update(`bsn:${bsn}`).digest();
}
