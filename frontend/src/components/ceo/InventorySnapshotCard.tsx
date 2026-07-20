import { Link } from "react-router-dom";
import { Boxes } from "lucide-react";

import SampleDataBadge from "@/components/SampleDataBadge";
import { MOCK_INVENTORY } from "@/mock/inventory";

export default function InventorySnapshotCard() {
  const outOfStock = MOCK_INVENTORY.filter((i) => i.onHand <= 0).length;
  const belowReorder = MOCK_INVENTORY.filter((i) => i.onHand > 0 && i.onHand <= i.reorderPoint).length;
  const healthy = MOCK_INVENTORY.length - outOfStock - belowReorder;
  const needsReorder = MOCK_INVENTORY.filter((i) => i.onHand <= i.reorderPoint).slice(0, 4);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Boxes className="h-4 w-4 text-jarvis-blue" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">INVENTORY</h2>
        </div>
        <SampleDataBadge />
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-xl border border-jarvis-rose/30 bg-jarvis-rose/5 p-2.5 text-center">
            <p className="font-data text-lg font-semibold text-jarvis-rose">{outOfStock}</p>
            <p className="text-[10px] uppercase tracking-wide text-jarvis-muted">Out</p>
          </div>
          <div className="rounded-xl border border-jarvis-amber/30 bg-jarvis-amber/5 p-2.5 text-center">
            <p className="font-data text-lg font-semibold text-jarvis-amber">{belowReorder}</p>
            <p className="text-[10px] uppercase tracking-wide text-jarvis-muted">Low</p>
          </div>
          <div className="rounded-xl border border-jarvis-emerald/30 bg-jarvis-emerald/5 p-2.5 text-center">
            <p className="font-data text-lg font-semibold text-jarvis-emerald">{healthy}</p>
            <p className="text-[10px] uppercase tracking-wide text-jarvis-muted">OK</p>
          </div>
        </div>
        {needsReorder.length > 0 && (
          <ul className="space-y-1">
            {needsReorder.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate text-jarvis-text">{item.name}</span>
                <span className="shrink-0 font-data text-jarvis-muted">
                  {item.onHand} on hand · reorder at {item.reorderPoint}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Link to="/company/inventory" className="inline-block text-xs font-medium text-jarvis-cyan hover:underline">
          Open Inventory →
        </Link>
      </div>
    </div>
  );
}
