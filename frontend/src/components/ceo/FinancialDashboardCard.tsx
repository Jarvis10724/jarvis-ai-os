import clsx from "clsx";
import { Link } from "react-router-dom";
import { Landmark } from "lucide-react";

import SampleDataBadge from "@/components/SampleDataBadge";
import { useCompany } from "@/context/CompanyContext";
import { MOCK_FINANCIAL_SUMMARY } from "@/mock/financials";
import { MOCK_SHOPIFY_SNAPSHOT } from "@/mock/shopify";
import { MOCK_LISTINGS } from "@/mock/amazonLaunch";

const QUICKBOOKS_STATUS_LABELS: Record<string, string> = {
  not_started: "Not connected",
  in_progress: "Setup in progress",
  needs_rebuild: "Needs review",
  done: "Connected",
};

function prettifyStatus(status: string): string {
  return QUICKBOOKS_STATUS_LABELS[status] ?? status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * One consolidated financial view: cash/revenue/expenses/profit and
 * Shopify/Amazon sales are sample data (real syncs land in Phase 3e/3f) —
 * QuickBooks has no live numbers yet either, but the company's own
 * `sections.quickbooks` status is real, so that's used as an honest
 * proxy instead of inventing a dollar figure.
 */
export default function FinancialDashboardCard() {
  const { activeCompany } = useCompany();
  const { revenue, expenses, profit, cashOnHand } = MOCK_FINANCIAL_SUMMARY;
  const amazonLive = MOCK_LISTINGS.filter((l) => l.status === "live").length;
  const qbStatus = activeCompany?.sections?.quickbooks?.status ?? null;

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Landmark className="h-4 w-4 text-jarvis-emerald" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            FINANCIAL DASHBOARD
          </h2>
        </div>
        <SampleDataBadge />
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 p-2.5">
            <p className="text-xs text-jarvis-muted">Cash on hand</p>
            <p className="mt-0.5 font-data text-base font-semibold text-jarvis-emerald">
              ${cashOnHand.toLocaleString()}
            </p>
          </div>
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 p-2.5">
            <p className="text-xs text-jarvis-muted">Profit (30d)</p>
            <p className={clsx("mt-0.5 font-data text-base font-semibold", profit >= 0 ? "text-jarvis-emerald" : "text-jarvis-rose")}>
              ${profit.toLocaleString()}
            </p>
          </div>
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 p-2.5">
            <p className="text-xs text-jarvis-muted">Revenue</p>
            <p className="mt-0.5 font-data text-sm text-jarvis-text">${revenue.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 p-2.5">
            <p className="text-xs text-jarvis-muted">Expenses</p>
            <p className="mt-0.5 font-data text-sm text-jarvis-text">${expenses.toLocaleString()}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2.5 py-2">
            <p className="text-jarvis-muted">Shopify (today)</p>
            <p className="font-data text-sm text-jarvis-text">
              {MOCK_SHOPIFY_SNAPSHOT.ordersToday} orders · ${MOCK_SHOPIFY_SNAPSHOT.revenueToday.toLocaleString()}
            </p>
          </div>
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2.5 py-2">
            <p className="text-jarvis-muted">Amazon</p>
            <p className="font-data text-sm text-jarvis-text">{amazonLive} listing(s) live</p>
          </div>
        </div>

        <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2.5 py-2 text-xs">
          <p className="text-jarvis-muted">QuickBooks</p>
          <p className="text-sm text-jarvis-text">{qbStatus ? prettifyStatus(qbStatus) : "No company selected"}</p>
        </div>

        <Link to="/company/financials" className="inline-block text-xs font-medium text-jarvis-cyan hover:underline">
          Open Financial Dashboard →
        </Link>
      </div>
    </div>
  );
}
