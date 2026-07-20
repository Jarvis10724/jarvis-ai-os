import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DollarSign } from "lucide-react";
import clsx from "clsx";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import DataTable, { type DataTableColumn } from "@/components/DataTable";
import ModulePageHeader from "@/components/ModulePageHeader";
import { MOCK_FINANCIAL_SUMMARY, MOCK_MONTHLY_TREND, MOCK_TRANSACTIONS } from "@/mock/financials";
import type { TransactionItem } from "@/types";

const COLUMNS: DataTableColumn<TransactionItem>[] = [
  { key: "date", label: "Date", render: (t) => t.date },
  { key: "description", label: "Description", render: (t) => t.description },
  { key: "category", label: "Category", render: (t) => t.category },
  {
    key: "amount",
    label: "Amount",
    render: (t) => (
      <span className={clsx("font-medium", t.type === "income" ? "text-jarvis-emerald" : "text-jarvis-rose")}>
        {t.type === "income" ? "+" : "-"}${t.amount.toLocaleString()}
      </span>
    ),
  },
];

export default function FinancialDashboardPage() {
  const s = MOCK_FINANCIAL_SUMMARY;
  const cards = [
    { label: "Revenue (30d)", value: `$${s.revenue.toLocaleString()}`, tone: "text-jarvis-text" },
    { label: "Expenses (30d)", value: `$${s.expenses.toLocaleString()}`, tone: "text-jarvis-text" },
    { label: "Profit (30d)", value: `$${s.profit.toLocaleString()}`, tone: "text-jarvis-emerald" },
    { label: "Cash on Hand", value: `$${s.cashOnHand.toLocaleString()}`, tone: "text-jarvis-cyan" },
  ];

  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={DollarSign}
            title="Financial Dashboard"
            description={`Revenue, expenses, and cash position for ${company.name} — as of ${s.asOf}.`}
          />

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {cards.map((c) => (
              <div key={c.label} className="hud-panel p-4">
                <p className="text-xs text-jarvis-muted">{c.label}</p>
                <p className={clsx("mt-1 font-display text-lg font-bold", c.tone)}>{c.value}</p>
              </div>
            ))}
          </div>

          <div className="hud-panel hud-corner h-56 shrink-0 p-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-jarvis-muted">Monthly Revenue Trend</p>
            <ResponsiveContainer width="100%" height="85%">
              <AreaChart data={MOCK_MONTHLY_TREND} margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="finGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "#64748b", fontSize: 11 }} />
                <YAxis hide domain={["dataMin - 1000", "dataMax + 1000"]} />
                <Tooltip
                  contentStyle={{ background: "#0b1120", border: "1px solid #1e293b", borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: "#e2e8f0" }}
                />
                <Area type="monotone" dataKey="value" stroke="#22d3ee" strokeWidth={2} fill="url(#finGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-hidden">
            <DataTable columns={COLUMNS} rows={MOCK_TRANSACTIONS} emptyLabel="No transactions yet." />
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
