import { useEffect, useState } from "react";
import { AlertOctagon } from "lucide-react";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { MOCK_CONTACTS } from "@/mock/crm";
import { MOCK_FINANCIAL_SUMMARY } from "@/mock/financials";
import type { Product } from "@/types";

interface IssueRow {
  label: string;
  value: string;
  real: boolean;
  severity: "rose" | "amber";
}

export default function UrgentIssuesCard() {
  const { companies } = useCompany();
  const [outOfStock, setOutOfStock] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let count = 0;
      for (const c of companies) {
        try {
          const products = await api.listProducts(c.id);
          count += products.filter((p: Product) => p.inventory !== null && p.inventory <= 0).length;
        } catch {
          // no products yet for this company — fine
        }
      }
      if (!cancelled) setOutOfStock(count);
    })();
    return () => {
      cancelled = true;
    };
  }, [companies]);

  const needsRebuild = companies.flatMap((c) =>
    Object.entries(c.sections)
      .filter(([, s]) => s.status === "needs_rebuild")
      .map(([key]) => `${c.name} · ${key}`)
  );
  const staleLeads = MOCK_CONTACTS.filter((c) => c.stage === "lead" || c.stage === "contacted").length;
  const lowCash = MOCK_FINANCIAL_SUMMARY.cashOnHand < 15_000;

  const rows: IssueRow[] = [
    ...(outOfStock > 0
      ? [{ label: "Real products out of stock", value: String(outOfStock), real: true, severity: "rose" as const }]
      : []),
    ...needsRebuild.map((label) => ({
      label: `Needs rebuild: ${label}`,
      value: "",
      real: true,
      severity: "rose" as const,
    })),
    { label: "CRM contacts waiting on follow-up", value: String(staleLeads), real: false, severity: "amber" as const },
    ...(lowCash
      ? [
          {
            label: "Cash on hand below $15k",
            value: `$${MOCK_FINANCIAL_SUMMARY.cashOnHand.toLocaleString()}`,
            real: false,
            severity: "rose" as const,
          },
        ]
      : []),
  ];

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 text-jarvis-rose" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">URGENT ISSUES</h2>
        </div>
      </div>
      <ul className="flex-1 space-y-2 overflow-y-auto p-4">
        {rows.map((row, i) => (
          <li
            key={i}
            className={clsx(
              "flex items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-sm text-jarvis-text",
              row.severity === "rose" ? "border-jarvis-rose/30 bg-jarvis-rose/5" : "border-jarvis-amber/30 bg-jarvis-amber/5"
            )}
          >
            <span className="truncate">{row.label}</span>
            <span className="flex shrink-0 items-center gap-2">
              {row.value && <span className="font-data text-xs text-jarvis-muted">{row.value}</span>}
              {!row.real && <SampleDataBadge />}
            </span>
          </li>
        ))}
        {rows.length === 0 && <p className="p-4 text-xs text-jarvis-muted">No urgent issues right now.</p>}
      </ul>
    </div>
  );
}
