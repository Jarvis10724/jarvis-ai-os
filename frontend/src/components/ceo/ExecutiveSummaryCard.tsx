import { useEffect, useState } from "react";
import { AlertTriangle, Flame, Lightbulb, Sparkles } from "lucide-react";
import { motion } from "framer-motion";

import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import type { ExecutiveSummary, Product } from "@/types";

function isToday(iso: string | null): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

/**
 * The "command center" briefing at the top of the CEO Dashboard — an
 * AI-generated summary, top 3 priorities, and urgent alerts, built ONLY
 * from real signals (unread email, pending approvals, today's meetings,
 * out-of-stock products, sections flagged needs-rebuild). Financials/
 * Shopify/Amazon/marketing numbers are deliberately left out of this
 * digest since those are still sample data (Phase 3e-g) — feeding fake
 * numbers into an "AI insight" would make it confidently wrong.
 */
export default function ExecutiveSummaryCard() {
  const { companies, activeCompany } = useCompany();
  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);

      let unreadCount = 0;
      let subjects: string[] = [];
      try {
        const unread = await api.listGmailMessages({ unreadOnly: true, maxResults: 10 });
        unreadCount = unread.length;
        subjects = unread.map((m) => m.subject || "(no subject)").slice(0, 5);
      } catch {
        // Gmail not connected — leave at 0 rather than guessing.
      }

      let meetingTitles: string[] = [];
      try {
        const events = await api.listCalendarEvents({ maxResults: 15 });
        meetingTitles = events.filter((e) => isToday(e.start)).map((e) => e.summary || "(untitled event)");
      } catch {
        // Calendar not connected — leave empty.
      }

      let pendingCount = 0;
      let approvalSummaries: string[] = [];
      try {
        const approvals = await api.listApprovals({ companyId: "any", status: "pending" });
        pendingCount = approvals.length;
        approvalSummaries = approvals.map((a) => `${a.capability_name}.${a.action_type}`).slice(0, 5);
      } catch {
        // Shouldn't happen (always available), but don't block the card on it.
      }

      const outOfStock: string[] = [];
      for (const c of companies) {
        try {
          const products = await api.listProducts(c.id);
          products
            .filter((p: Product) => p.inventory !== null && p.inventory <= 0 && p.launch_status !== "not_started")
            .forEach((p) => outOfStock.push(`${p.name} (${c.name})`));
        } catch {
          // no products endpoint access for this company yet — skip
        }
      }

      const needsRebuild = companies.flatMap((c) =>
        Object.entries(c.sections)
          .filter(([, s]) => s.status === "needs_rebuild")
          .map(([key]) => `${c.name} · ${key}`)
      );

      try {
        const result = await api.getExecutiveSummary({
          company_name: activeCompany?.name ?? null,
          unread_email_count: unreadCount,
          email_subjects: subjects,
          pending_approvals_count: pendingCount,
          approval_summaries: approvalSummaries,
          todays_meeting_titles: meetingTitles,
          out_of_stock_products: outOfStock,
          needs_rebuild_sections: needsRebuild,
        });
        if (!cancelled) setSummary(result);
      } catch {
        if (!cancelled) setError("Couldn't generate today's briefing — check the AI provider's API key in Settings.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companies, activeCompany?.id]);

  return (
    <div className="hud-panel hud-corner overflow-hidden">
      <div className="flex items-center gap-2 border-b border-jarvis-border/60 px-5 py-4">
        <Sparkles className="h-4 w-4 text-jarvis-cyan" />
        <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
          EXECUTIVE SUMMARY
        </h2>
      </div>

      <div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <p className="mb-1 text-[11px] uppercase tracking-wide text-jarvis-muted">Today</p>
          {loading ? (
            <div className="h-4 w-full animate-pulse rounded bg-jarvis-panel2/60" />
          ) : error ? (
            <p className="text-sm text-jarvis-rose">{error}</p>
          ) : (
            <p className="text-sm leading-relaxed text-jarvis-text">{summary?.summary}</p>
          )}
        </div>

        <div className="lg:col-span-1">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-jarvis-muted">
            <Flame className="h-3 w-3 text-jarvis-amber" /> Top 3 priorities
          </p>
          <ul className="space-y-1.5">
            {loading
              ? [0, 1, 2].map((i) => <div key={i} className="h-3.5 w-4/5 animate-pulse rounded bg-jarvis-panel2/60" />)
              : (summary?.priorities ?? []).map((p, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.05 * i }}
                    className="flex items-start gap-2 text-sm text-jarvis-text"
                  >
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 font-data text-[9px] font-bold text-jarvis-cyan">
                      {i + 1}
                    </span>
                    {p}
                  </motion.li>
                ))}
          </ul>
        </div>

        <div className="lg:col-span-1">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-jarvis-muted">
            <AlertTriangle className="h-3 w-3 text-jarvis-rose" /> Urgent alerts
          </p>
          {loading ? (
            <div className="h-3.5 w-3/4 animate-pulse rounded bg-jarvis-panel2/60" />
          ) : (summary?.alerts?.length ?? 0) === 0 ? (
            <p className="text-xs text-jarvis-muted">Nothing urgent right now.</p>
          ) : (
            <ul className="space-y-1.5">
              {summary!.alerts.map((a, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-jarvis-rose/30 bg-jarvis-rose/5 px-2.5 py-1.5 text-xs text-jarvis-text"
                >
                  {a}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="lg:col-span-1">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-jarvis-muted">
            <Lightbulb className="h-3 w-3 text-jarvis-cyan" /> Daily recommendations
          </p>
          {loading ? (
            <div className="h-3.5 w-3/4 animate-pulse rounded bg-jarvis-panel2/60" />
          ) : (
            <ul className="space-y-1.5">
              {(summary?.recommendations ?? []).map((r, i) => (
                <li key={i} className="text-xs text-jarvis-muted">
                  {r}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
