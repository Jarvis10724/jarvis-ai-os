import { Wallet } from "lucide-react";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import { MOCK_FINANCIAL_SUMMARY } from "@/mock/financials";

export default function CashSnapshotCard() {
  const { revenue, expenses, profit, cashOnHand } = MOCK_FINANCIAL_SUMMARY;

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-jarvis-emerald" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">CASH</h2>
        </div>
        <SampleDataBadge />
      </div>
      <div className="grid flex-1 grid-cols-2 gap-3 p-4">
        <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
          <p className="text-xs text-jarvis-muted">On hand</p>
          <p className="mt-1 font-data text-lg font-semibold text-jarvis-emerald">
            ${cashOnHand.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
          <p className="text-xs text-jarvis-muted">Profit (30d)</p>
          <p className={clsx("mt-1 font-data text-lg font-semibold", profit >= 0 ? "text-jarvis-emerald" : "text-jarvis-rose")}>
            ${profit.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
          <p className="text-xs text-jarvis-muted">Revenue</p>
          <p className="mt-1 font-data text-sm font-medium text-jarvis-text">${revenue.toLocaleString()}</p>
        </div>
        <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
          <p className="text-xs text-jarvis-muted">Expenses</p>
          <p className="mt-1 font-data text-sm font-medium text-jarvis-text">${expenses.toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
}
