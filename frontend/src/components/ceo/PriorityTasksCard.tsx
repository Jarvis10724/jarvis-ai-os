import { useEffect, useState } from "react";
import { Flame } from "lucide-react";
import { motion } from "framer-motion";

import SampleDataBadge from "@/components/SampleDataBadge";
import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { MOCK_PROJECTS } from "@/mock/projects";
import type { Product } from "@/types";

interface PriorityItem {
  id: string;
  title: string;
  reason: string;
  score: number;
  real: boolean;
}

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  return Math.round((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
}

/**
 * "Today's highest-ROI tasks" — v1 is a deterministic heuristic over real
 * data (out-of-stock launched products, company sections flagged
 * needs-rebuild) blended with sample project due-dates. Full AI-driven
 * ranking (weighing all of this against actual expected business impact)
 * is Phase 10 — the AI CEO Brain — once more real signals exist to rank
 * against.
 */
export default function PriorityTasksCard() {
  const { companies } = useCompany();
  const [products, setProducts] = useState<(Product & { companyName: string })[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const all: (Product & { companyName: string })[] = [];
      for (const c of companies) {
        try {
          const list = await api.listProducts(c.id);
          list.forEach((p) => all.push({ ...p, companyName: c.name }));
        } catch {
          // Company may have no products endpoint access yet — skip quietly.
        }
      }
      if (!cancelled) setProducts(all);
    })();
    return () => {
      cancelled = true;
    };
  }, [companies]);

  const items: PriorityItem[] = [];

  products.forEach((p) => {
    if (p.inventory !== null && p.inventory <= 0 && p.launch_status !== "not_started") {
      items.push({
        id: `prod-${p.id}`,
        title: `Restock "${p.name}" — out of stock`,
        reason: `${p.companyName} · zero inventory on a launched product`,
        score: 95,
        real: true,
      });
    }
  });

  companies.forEach((c) => {
    Object.entries(c.sections).forEach(([key, section]) => {
      if (section.status === "needs_rebuild") {
        items.push({
          id: `sec-${c.id}-${key}`,
          title: `Rebuild ${key} for ${c.name}`,
          reason: "Flagged needs-rebuild in Company Profile",
          score: 85,
          real: true,
        });
      }
    });
  });

  MOCK_PROJECTS.filter((p) => p.status !== "done" && p.dueDate).forEach((p) => {
    const d = daysUntil(p.dueDate);
    if (d === null) return;
    items.push({
      id: `proj-${p.id}`,
      title: p.title,
      reason: d < 0 ? `Overdue by ${Math.abs(d)}d` : `Due in ${d}d`,
      score: Math.max(10, 70 - d * 3),
      real: false,
    });
  });

  const ranked = items.sort((a, b) => b.score - a.score).slice(0, 5);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Flame className="h-4 w-4 text-jarvis-amber" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            HIGHEST-ROI TASKS
          </h2>
        </div>
        <p className="mt-1 text-[11px] text-jarvis-muted">
          Heuristic ranking today — full AI ranking arrives with the CEO Brain phase.
        </p>
      </div>
      <ul className="flex-1 space-y-2 overflow-y-auto p-4">
        {ranked.map((item, i) => (
          <motion.li
            key={item.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.04 * i, duration: 0.3 }}
            className="flex items-start gap-3 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2.5"
          >
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 font-data text-[10px] font-bold text-jarvis-cyan">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-jarvis-text">{item.title}</p>
              <p className="text-xs text-jarvis-muted">{item.reason}</p>
            </div>
            {!item.real && <SampleDataBadge />}
          </motion.li>
        ))}
        {ranked.length === 0 && (
          <p className="p-4 text-xs text-jarvis-muted">Nothing urgent — clean slate.</p>
        )}
      </ul>
    </div>
  );
}
