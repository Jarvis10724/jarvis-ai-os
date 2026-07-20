import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, ShoppingBag, XCircle } from "lucide-react";

import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import type { ShopifyStatus } from "@/types";

/**
 * Read-only Shopify connection status for the Settings page. Shows only
 * non-secret signals (configured?, store domain, read-only flag, whether the
 * active workspace is the bound one) — the Admin API token never reaches the
 * frontend. Purely informational in Phase 1: no connect/disconnect button,
 * because connection is done by setting env vars on the server, not through
 * the UI.
 */
export default function ShopifyStatusCard() {
  const { activeCompanyId } = useCompany();
  const [status, setStatus] = useState<ShopifyStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getShopifyStatus(activeCompanyId ?? undefined)
      .then((s) => !cancelled && setStatus(s))
      .catch(() => !cancelled && setStatus(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [activeCompanyId]);

  return (
    <div className="hud-panel hud-corner shrink-0 p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShoppingBag className="h-4 w-4 text-jarvis-cyan" />
          <p className="text-xs uppercase tracking-wide text-jarvis-muted">Shopify (read-only)</p>
        </div>
        {status?.read_only && (
          <span className="rounded-full border border-jarvis-border/70 bg-jarvis-panel2/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-muted">
            Read-only
          </span>
        )}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-jarvis-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Checking…
        </div>
      ) : !status?.configured ? (
        <div className="flex items-start gap-2">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-jarvis-muted" />
          <div>
            <p className="text-sm text-jarvis-text">Not connected</p>
            <p className="text-xs text-jarvis-muted">
              Set <code>SHOPIFY_STORE_DOMAIN</code>, <code>SHOPIFY_ADMIN_API_TOKEN</code>, and{" "}
              <code>SHOPIFY_WORKSPACE_ID</code> in the backend <code>.env</code>, then restart the server.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-jarvis-emerald" />
            <p className="text-sm text-jarvis-text">
              Connected to <span className="font-medium">{status.store_domain}</span>
            </p>
          </div>
          <p className="text-xs text-jarvis-muted">
            API version {status.api_version} ·{" "}
            {status.active_workspace_is_bound ? (
              <span className="text-jarvis-emerald">Bound to the active workspace</span>
            ) : (
              <span className="text-jarvis-amber">
                Bound to another workspace — switch to it to view store data
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
