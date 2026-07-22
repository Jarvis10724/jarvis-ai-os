import { useCallback, useEffect, useState } from "react";
import { Boxes, Layers, Lock, Package, RefreshCw, Store } from "lucide-react";

import { api, ApiError } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill from "@/components/StatusPill";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import type { BrandBrainSummary, BrandCollection, BrandProduct, ShopifyStatus } from "@/types";

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "Never synced";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "Synced just now";
  if (mins < 60) return `Synced ${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `Synced ${hrs}h ago`;
  return `Synced ${Math.round(hrs / 24)}d ago`;
}

/**
 * Brand Brain — the workspace's structured source of truth, mirrored read-only
 * from Shopify. Shows connection state, store identity, and the imported
 * catalog; the Sync button pulls the latest (never writes to the store).
 */
export default function BrandBrainPage() {
  const { activeCompany, activeCompanyId } = useCompany();
  const toast = useToast();

  const [status, setStatus] = useState<ShopifyStatus | null>(null);
  const [summary, setSummary] = useState<BrandBrainSummary | null>(null);
  const [products, setProducts] = useState<BrandProduct[]>([]);
  const [collections, setCollections] = useState<BrandCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    if (!activeCompanyId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [st, sum, prods, cols] = await Promise.all([
        api.getShopifyStatus(activeCompanyId).catch(() => null),
        api.getBrandBrain(activeCompanyId).catch(() => null),
        api.listBrandProducts(activeCompanyId).catch(() => []),
        api.listBrandCollections(activeCompanyId).catch(() => []),
      ]);
      setStatus(st);
      setSummary(sum);
      setProducts(prods ?? []);
      setCollections(cols ?? []);
    } finally {
      setLoading(false);
    }
  }, [activeCompanyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function sync() {
    if (!activeCompanyId) return;
    setSyncing(true);
    try {
      const res = await api.syncBrandBrain(activeCompanyId);
      const mem = res.memory_entries ? ` · ${res.memory_entries} added to AI memory` : "";
      toast.push(`Imported ${res.product_count} products, ${res.collection_count} collections${mem}.`, "success");
      await load();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Sync failed.", "error");
    } finally {
      setSyncing(false);
    }
  }

  const bound = status?.configured && status?.active_workspace_is_bound;

  if (!activeCompanyId) {
    return (
      <main className="flex h-full flex-1 items-center justify-center p-6 text-center text-sm text-jarvis-muted">
        Select a workspace to view its Brand Brain.
      </main>
    );
  }

  return (
    <main className="h-full min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
      <ModulePageHeader
        icon={Boxes}
        title="Brand Brain"
        description="Your workspace's structured source of truth — products, collections, pricing, and store metadata, mirrored read-only from Shopify."
        sampleData={false}
        actions={
          bound ? (
            <button
              onClick={sync}
              disabled={syncing}
              className="press-scale flex items-center gap-2 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3.5 py-2 text-sm font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
            >
              <RefreshCw className={syncing ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              {syncing ? "Syncing…" : "Sync from Shopify"}
            </button>
          ) : undefined
        }
      />

      {/* Connection + read-only state */}
      <div className="hud-panel hud-corner flex flex-wrap items-center gap-3 p-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-jarvis-cyan/10 text-jarvis-cyan">
          <Store className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-jarvis-text">
            {summary?.store_name || activeCompany?.name || "Workspace"}
          </p>
          <p className="truncate text-xs text-jarvis-muted">
            {status?.store_domain || "Shopify not connected"}
            {summary?.exists ? ` · ${timeAgo(summary.last_synced_at)}` : ""}
          </p>
        </div>
        <StatusPill label={bound ? "Connected" : "Not connected"} tone={bound ? "success" : "neutral"} />
        <span className="inline-flex items-center gap-1 rounded-lg border border-jarvis-amber/40 bg-jarvis-amber/10 px-2.5 py-1 text-[11px] font-semibold text-jarvis-amber">
          <Lock className="h-3 w-3" /> Read-only
        </span>
      </div>

      {/* Setup guidance when not yet connected — no secrets handled in the app. */}
      {!bound && !loading && (
        <div className="hud-panel hud-corner p-4 text-sm text-jarvis-muted">
          <p className="mb-2 font-semibold text-jarvis-text">Connect this workspace's Shopify store</p>
          <p className="mb-2">
            Add these to the backend <code>.env</code> (credentials live only there — never in the app, UI, or
            git), then restart the backend and press <span className="text-jarvis-cyan">Sync from Shopify</span>:
          </p>
          <ul className="list-inside list-disc space-y-1 text-xs">
            <li><code>SHOPIFY_STORE_DOMAIN</code> — e.g. primal-penni.myshopify.com</li>
            <li><code>SHOPIFY_CLIENT_ID</code> + <code>SHOPIFY_CLIENT_SECRET</code> (Dev Dashboard app), or a legacy <code>SHOPIFY_ADMIN_API_TOKEN</code></li>
            <li><code>SHOPIFY_WORKSPACE_ID</code> = <code>{activeCompanyId}</code> (this workspace)</li>
          </ul>
          <p className="mt-2 text-xs">The app uses read scopes only; write operations stay disabled.</p>
        </div>
      )}

      {/* Counts */}
      {summary?.exists && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatCard icon={Package} label="Products" value={summary.product_count ?? products.length} />
          <StatCard icon={Layers} label="Collections" value={summary.collection_count ?? collections.length} />
          <StatCard icon={Store} label="Currency" value={summary.currency || "—"} />
        </div>
      )}

      {loading && <div className="skeleton h-40 rounded-2xl" />}

      {/* Products */}
      {!loading && products.length > 0 && (
        <section>
          <h2 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-widest text-jarvis-faint">
            Products
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {products.map((p) => (
              <div key={p.id} className="hud-corner overflow-hidden rounded-2xl border border-jarvis-border/60 bg-jarvis-panel/50">
                <div className="aspect-square w-full bg-jarvis-panel2/40">
                  {p.featured_image ? (
                    <img src={p.featured_image} alt={p.title} className="h-full w-full object-cover" loading="lazy" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-jarvis-faint">
                      <Package className="h-8 w-8" />
                    </div>
                  )}
                </div>
                <div className="p-3">
                  <p className="truncate text-sm font-medium text-jarvis-text">{p.title}</p>
                  <p className="mt-0.5 text-xs text-jarvis-muted">
                    {p.price_min != null ? `${p.price_min.toFixed(2)} ${p.currency ?? ""}`.trim() : "—"}
                    {p.total_inventory != null ? ` · ${p.total_inventory} in stock` : ""}
                  </p>
                  {p.tags.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {p.tags.slice(0, 3).map((t) => (
                        <span key={t} className="rounded bg-jarvis-panel2/60 px-1.5 py-0.5 text-[9px] text-jarvis-muted">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Collections */}
      {!loading && collections.length > 0 && (
        <section>
          <h2 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-widest text-jarvis-faint">
            Collections
          </h2>
          <div className="flex flex-wrap gap-2">
            {collections.map((c) => (
              <span key={c.id} className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-1.5 text-xs text-jarvis-text">
                {c.title}
                {c.products_count != null && <span className="ml-1 text-jarvis-muted">· {c.products_count}</span>}
              </span>
            ))}
          </div>
        </section>
      )}

      {!loading && bound && !summary?.exists && (
        <div className="hud-panel hud-corner p-8 text-center text-sm text-jarvis-muted">
          Connected. Press <span className="text-jarvis-cyan">Sync from Shopify</span> to import your catalog into the Brand Brain.
        </div>
      )}
    </main>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string | number }) {
  return (
    <div className="hud-panel hud-corner flex items-center gap-3 p-3.5">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-jarvis-cyan/10 text-jarvis-cyan">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-lg font-bold text-jarvis-text">{value}</p>
        <p className="text-[11px] uppercase tracking-wide text-jarvis-muted">{label}</p>
      </div>
    </div>
  );
}
