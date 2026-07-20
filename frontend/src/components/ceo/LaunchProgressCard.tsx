import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Rocket } from "lucide-react";
import clsx from "clsx";

import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import type { Product } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  not_started: "border-jarvis-muted/40 bg-jarvis-muted/10 text-jarvis-muted",
  in_progress: "border-jarvis-amber/40 bg-jarvis-amber/10 text-jarvis-amber",
  needs_rebuild: "border-jarvis-rose/40 bg-jarvis-rose/10 text-jarvis-rose",
  done: "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald",
};

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        STATUS_STYLES[status] ?? STATUS_STYLES.not_started
      )}
    >
      {statusLabel(status)}
    </span>
  );
}

/**
 * Launch tracking for the Primal Penni company workspace — all real data:
 * per-product launch_status/manufacturer/packaging fields, the company's
 * own section statuses (manufacturing, packaging, brand/website, amazon),
 * and checklist completion. Resolves the company by name match rather than
 * a hardcoded id so it keeps working if the company is renamed or re-seeded.
 */
export default function LaunchProgressCard() {
  const { companies } = useCompany();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  const company = companies.find((c) => c.name.toLowerCase().includes("primal penni"));

  useEffect(() => {
    if (!company) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const list = await api.listProducts(company.id);
        if (!cancelled) setProducts(list);
      } catch {
        // no products yet
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [company?.id]);

  if (!company) {
    return (
      <div className="hud-panel hud-corner flex h-full flex-col items-center justify-center gap-2 p-4 text-center">
        <Rocket className="h-5 w-5 text-jarvis-muted" />
        <p className="text-xs text-jarvis-muted">No "Primal Penni" company workspace found yet.</p>
      </div>
    );
  }

  const withManufacturer = products.filter((p) => p.manufacturer).length;
  const withPackaging = products.filter((p) => p.packaging).length;
  const launched = products.filter((p) => p.launch_status === "launched" || p.launch_status === "ready").length;

  const checklists = Object.values(company.checklists);
  const totalChecklistItems = checklists.reduce((sum, items) => sum + items.length, 0);
  const doneChecklistItems = checklists.reduce((sum, items) => sum + items.filter((i) => i.done).length, 0);
  const checklistPct = totalChecklistItems > 0 ? Math.round((doneChecklistItems / totalChecklistItems) * 100) : 0;

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Rocket className="h-4 w-4 text-jarvis-cyan" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            {company.name.toUpperCase()} LAUNCH
          </h2>
        </div>
        <Link to="/company/dashboard" className="text-xs font-medium text-jarvis-cyan hover:underline">
          Open →
        </Link>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-wide text-jarvis-muted">Product development</p>
            <span className="font-data text-xs text-jarvis-text">
              {loading ? "…" : `${launched}/${products.length} launch-ready`}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-jarvis-panel2/60">
            <div
              className="h-full rounded-full bg-jarvis-cyan transition-all duration-500"
              style={{ width: `${products.length ? (launched / products.length) * 100 : 0}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2.5 py-2">
            <p className="text-jarvis-muted">Manufacturer set</p>
            <p className="font-data text-sm text-jarvis-text">
              {loading ? "…" : `${withManufacturer}/${products.length}`}
            </p>
          </div>
          <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2.5 py-2">
            <p className="text-jarvis-muted">Packaging set</p>
            <p className="font-data text-sm text-jarvis-text">
              {loading ? "…" : `${withPackaging}/${products.length}`}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {company.sections.brand && (
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-jarvis-muted">Website:</span>
              <StatusPill status={company.sections.brand.status} />
            </div>
          )}
          {company.sections.amazon && (
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-jarvis-muted">Amazon:</span>
              <StatusPill status={company.sections.amazon.status} />
            </div>
          )}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-wide text-jarvis-muted">Launch checklist</p>
            <span className="font-data text-xs text-jarvis-text">{checklistPct}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-jarvis-panel2/60">
            <div
              className="h-full rounded-full bg-jarvis-emerald transition-all duration-500"
              style={{ width: `${checklistPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
