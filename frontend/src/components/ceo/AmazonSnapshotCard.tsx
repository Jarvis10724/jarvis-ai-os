import { Link } from "react-router-dom";
import { Package } from "lucide-react";

import SampleDataBadge from "@/components/SampleDataBadge";
import { AMAZON_STATUS_LABELS, MOCK_LISTINGS } from "@/mock/amazonLaunch";

export default function AmazonSnapshotCard() {
  const live = MOCK_LISTINGS.filter((l) => l.status === "live").length;
  const inProgress = MOCK_LISTINGS.filter((l) => l.status !== "live").length;

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Package className="h-4 w-4 text-jarvis-amber" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">AMAZON</h2>
        </div>
        <SampleDataBadge />
      </div>
      <div className="flex-1 space-y-2 p-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
            <p className="text-xs text-jarvis-muted">Live listings</p>
            <p className="mt-1 font-data text-lg font-semibold text-jarvis-text">{live}</p>
          </div>
          <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
            <p className="text-xs text-jarvis-muted">In progress</p>
            <p className="mt-1 font-data text-lg font-semibold text-jarvis-text">{inProgress}</p>
          </div>
        </div>
        <ul className="space-y-1">
          {MOCK_LISTINGS.slice(0, 2).map((l) => (
            <li key={l.id} className="truncate text-xs text-jarvis-muted">
              {l.title} — <span className="text-jarvis-text">{AMAZON_STATUS_LABELS[l.status]}</span>
            </li>
          ))}
        </ul>
        <Link to="/company/amazon-launch" className="inline-block text-xs font-medium text-jarvis-cyan hover:underline">
          Open Amazon Launch Center →
        </Link>
      </div>
    </div>
  );
}
