import type { Company } from "@/types";

/**
 * Context-aware module visibility. Each company workspace only surfaces the
 * modules relevant to that business, so the AI-OS shell re-scopes what's
 * available as you switch workspaces (no per-company hardcoding by name).
 *
 * Investment/market modules (Stocks, Market News, the Investment Dashboard) are
 * reserved for businesses that actually do investing — detected from the
 * company's own profile (its industry or divisions). e.g. Greener Capitol
 * Solutions LLC carries an "Investing" division and shows them; SPN Group LLC
 * (Consumer Goods / Primal Penni) does not.
 */
export function showsInvestments(company: Company | null | undefined): boolean {
  if (!company) return false;
  const haystack = [company.industry ?? "", ...(company.divisions ?? [])]
    .join(" ")
    .toLowerCase();
  return /invest|market|portfolio|trading|securit|wealth|finance|fund|equit/.test(haystack);
}

/** A nav entry may declare which module category it belongs to, so surfaces can
 *  filter it out for companies that don't use that category. */
export type ModuleCategory = "investing";

export function isModuleVisibleForCompany(
  category: ModuleCategory | undefined,
  company: Company | null | undefined
): boolean {
  if (!category) return true;
  if (category === "investing") return showsInvestments(company);
  return true;
}
