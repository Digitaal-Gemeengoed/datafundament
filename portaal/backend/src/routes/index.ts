import type { FastifyInstance } from "fastify";
import { toegang } from "../toegang.js";
import { authRoutes } from "./auth.js";
import { noodRoutes } from "./nood.js";
import { accountRoutes } from "./accounts.js";
import { groepRoutes } from "./groepen.js";
import { profielRoutes } from "./profiel.js";
import { auditRoutes } from "./audit.js";
import { instellingRoutes } from "./instellingen.js";
import { platformRoutes } from "./platform.js";
import { dataproductRoutes } from "./dataproducten.js";
import { toegangRoutes } from "./toegang.js";
import { verwijderRoutes } from "./verwijderen.js";
import { datavraagRoutes } from "./datavragen.js";

/** Alle routes, in volgorde; de toegangscontrole eerst. */
export const routes: ((app: FastifyInstance) => Promise<void>)[] = [toegang, authRoutes, noodRoutes, accountRoutes, groepRoutes, profielRoutes, auditRoutes, instellingRoutes, platformRoutes, dataproductRoutes, toegangRoutes, verwijderRoutes, datavraagRoutes];
