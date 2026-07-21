import type { Company } from "@/types";
import { themeForCompany, type WorkspaceTheme } from "@/lib/workspaceTheme";

/**
 * Workspace architecture
 * ----------------------
 * Jarvis is organized around **workspaces**, not just legal entities. A
 * workspace can be a parent/innovation company, an operating consumer-brand
 * company, an investment portfolio, a real-estate portfolio, or a new venture
 * under validation. Every workspace shares the same AI Core and shell but has
 * its own identity, accent (see lib/workspaceTheme), relevant module set, and
 * — as integrations come online — its own memory/files/approvals/automations.
 *
 * Like the theming layer, a workspace's *kind* is derived on the frontend from
 * the company's own profile (name/industry/divisions), so there is NO backend
 * field or migration today. When an explicit `Company.kind` is added later,
 * `classifyWorkspace` can prefer it and every caller keeps working unchanged.
 *
 * Design intent (so future integrations attach to the right workspace without a
 * redesign):
 *   - `WorkspaceKind` classifies the workspace.
 *   - `capabilitiesFor(kind)` declares which module categories the workspace
 *     surfaces — consumed by nav gating (see moduleSurfacesForKind).
 *   - `INTEGRATION_FOCUS[kind]` declares which integration categories are
 *     typical for the workspace — consumed by the Integrations surface. The
 *     backend already scopes every integration per-company, so wiring a new
 *     integration to a workspace is data, not a redesign.
 */

export type WorkspaceKind =
  | "innovation-hub" // parent company: ideas, research, investments, real estate, funding, incubation
  | "consumer-brands" // operating company: products, Shopify, manufacturing, marketing, support, ops
  | "investment" // a standalone investment / securities portfolio
  | "real-estate" // a real-estate portfolio
  | "venture" // a new business under validation
  | "business"; // generic business (default)

export interface WorkspaceKindMeta {
  /** Short identity label shown under the AI Core, e.g. "Innovation Hub". */
  role: string;
  /** One line describing what the workspace is for. */
  purpose: string;
}

export const WORKSPACE_KIND_META: Record<WorkspaceKind, WorkspaceKindMeta> = {
  "innovation-hub": {
    role: "Innovation Hub",
    purpose: "Ideas, research, investments, real estate, funding, and new-venture incubation.",
  },
  "consumer-brands": {
    role: "Consumer Brands",
    purpose: "Products, Shopify, manufacturing, marketing, support, and operations.",
  },
  investment: {
    role: "Investment Portfolio",
    purpose: "Positions, watchlists, theses, and portfolio performance.",
  },
  "real-estate": {
    role: "Real Estate Portfolio",
    purpose: "Properties, deals, financing, and asset performance.",
  },
  venture: {
    role: "New Venture",
    purpose: "A new business under validation — research, model, and go-to-market.",
  },
  business: {
    role: "Business Workspace",
    purpose: "Operations, projects, and knowledge for this business.",
  },
};

/**
 * Module categories a workspace can surface. Nav entries tag themselves with a
 * category (or leave it undefined = always available), and a workspace only
 * shows the categories in its capability set. "core" modules (memory, files,
 * approvals, calendar, mail, tasks, contacts, chat) are available everywhere.
 */
export type WorkspaceCapability =
  | "core"
  | "operations" // company dashboard, projects, SOPs, CRM
  | "commerce" // Shopify/website/Amazon storefronts
  | "manufacturing" // manufacturing tracker, inventory
  | "marketing" // marketing studio, content calendar
  | "finance" // financial dashboard, QuickBooks
  | "investing" // investment dashboard, markets, brokerage
  | "incubation"; // idea incubator, research, new-venture validation

const CAPABILITIES: Record<WorkspaceKind, WorkspaceCapability[]> = {
  "innovation-hub": ["core", "operations", "finance", "investing", "incubation"],
  "consumer-brands": ["core", "operations", "commerce", "manufacturing", "marketing", "finance"],
  investment: ["core", "finance", "investing"],
  "real-estate": ["core", "operations", "finance"],
  venture: ["core", "operations", "commerce", "marketing", "incubation"],
  business: ["core", "operations", "commerce", "manufacturing", "marketing", "finance"],
};

export function capabilitiesFor(kind: WorkspaceKind): WorkspaceCapability[] {
  return CAPABILITIES[kind];
}

/**
 * Should a module tagged with `capability` be surfaced for a workspace of
 * `kind`? Untagged modules (undefined) are always shown.
 */
export function moduleSurfacesForKind(
  capability: WorkspaceCapability | undefined,
  kind: WorkspaceKind
): boolean {
  if (!capability || capability === "core") return true;
  return CAPABILITIES[kind].includes(capability);
}

/**
 * Integration categories typical for each workspace kind. Descriptive
 * (category-level), so the Integrations surface can recommend/group without
 * hardcoding backend integration names — the backend registry stays the source
 * of truth for what actually exists and its per-company connection state.
 */
export const INTEGRATION_FOCUS: Record<WorkspaceKind, string[]> = {
  "innovation-hub": ["Email", "Calendar", "Drive", "QuickBooks", "Brokerage", "Research"],
  "consumer-brands": ["Shopify", "Email", "Calendar", "Drive", "QuickBooks", "Amazon", "Social Ads", "Manufacturers"],
  investment: ["Email", "Brokerage", "Drive", "Market Data"],
  "real-estate": ["Email", "Drive", "QuickBooks", "Listing Portals"],
  venture: ["Email", "Calendar", "Drive", "Shopify", "Social Ads"],
  business: ["Email", "Calendar", "Drive", "QuickBooks"],
};

function haystack(company: Company): string {
  return [company.name, company.industry ?? "", company.tagline ?? "", ...(company.divisions ?? [])]
    .join(" ")
    .toLowerCase();
}

/**
 * Classify a workspace from its own profile — heuristic and order-sensitive
 * (more specific kinds are tested first). No backend field; a future explicit
 * `Company.kind` should be preferred here when present.
 */
const VALID_KINDS: WorkspaceKind[] = [
  "innovation-hub",
  "consumer-brands",
  "investment",
  "real-estate",
  "venture",
  "business",
];

export function classifyWorkspace(company: Company | null | undefined): WorkspaceKind {
  if (!company) return "business";
  // Prefer explicit structured metadata (company_type) — the heuristic is only
  // a fallback for workspaces that haven't been classified yet.
  const explicit = company.company_type as WorkspaceKind | null | undefined;
  if (explicit && VALID_KINDS.includes(explicit)) return explicit;
  const h = haystack(company);
  if (/real\s?estate|realty|propert|reit/.test(h)) return "real-estate";
  if (/consumer|goods|brand|retail|commerce|cpg|apparel|beauty|cosmetic|merch|dtc|e-?commerce/.test(h))
    return "consumer-brands";
  if (/capital|capitol|holding|ventures?|innovation|incubat|solutions|invest|fund|equit|portfolio|wealth/.test(h)) {
    // Pure portfolio vs. a broader parent/innovation hub.
    const portfolioOnly =
      /portfolio|watchlist|securit|trading|equit/.test(h) &&
      !/solution|holding|group|innovation|incubat/.test(h);
    return portfolioOnly ? "investment" : "innovation-hub";
  }
  if (/venture|startup|labs|prototype|r&d/.test(h)) return "venture";
  return "business";
}

export interface ResolvedWorkspace {
  company: Company | null;
  theme: WorkspaceTheme;
  kind: WorkspaceKind;
  /** Short role label ("Innovation Hub"). */
  role: string;
  /** One-line purpose. */
  purpose: string;
  /** 1–2 letter monogram "logo". */
  monogram: string;
  capabilities: WorkspaceCapability[];
  integrationFocus: string[];
}

/**
 * One call the UI uses to get everything about the active workspace: its
 * theme (accent + monogram), kind, identity labels, capabilities, and typical
 * integrations. With no active company, resolves to the neutral "Jarvis" OS.
 */
export function resolveWorkspace(company: Company | null | undefined): ResolvedWorkspace {
  const theme = themeForCompany(company);
  const kind = classifyWorkspace(company);
  const meta = WORKSPACE_KIND_META[kind];
  return {
    company: company ?? null,
    theme,
    kind,
    role: company ? meta.role : "AI Operating System",
    purpose: company ? meta.purpose : "Your unified command center across every workspace.",
    monogram: theme.monogram,
    capabilities: capabilitiesFor(kind),
    integrationFocus: INTEGRATION_FOCUS[kind],
  };
}
