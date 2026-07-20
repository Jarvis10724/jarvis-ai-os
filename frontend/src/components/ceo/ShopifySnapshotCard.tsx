import { Link } from "react-router-dom";
import { ShoppingBag } from "lucide-react";

import SampleDataBadge from "@/components/SampleDataBadge";
import { MOCK_SHOPIFY_SNAPSHOT } from "@/mock/shopify";

export default function ShopifySnapshotCard() {
  const { ordersToday, revenueToday, abandonedCarts, topProduct } = MOCK_SHOPIFY_SNAPSHOT;

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <ShoppingBag className="h-4 w-4 text-jarvis-emerald" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">SHOPIFY</h2>
        </div>
        <SampleDataBadge />
      </div>
      <div className="flex-1 space-y-3 p-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
            <p className="text-xs text-jarvis-muted">Orders today</p>
            <p className="mt-1 font-data text-lg font-semibold text-jarvis-text">{ordersToday}</p>
          </div>
          <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
            <p className="text-xs text-jarvis-muted">Revenue today</p>
            <p className="mt-1 font-data text-lg font-semibold text-jarvis-emerald">${revenueToday.toLocaleString()}</p>
          </div>
        </div>
        <p className="text-xs text-jarvis-muted">
          {abandonedCarts} abandoned carts · top seller: {topProduct}
        </p>
        <Link
          to="/integrations"
          className="inline-block text-xs font-medium text-jarvis-cyan hover:underline"
        >
          Connect Shopify for live data →
        </Link>
      </div>
    </div>
  );
}
