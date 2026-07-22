import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, BrainCircuit, Loader2, Play, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";

import { api, ApiError } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import type { WorkspaceIntelligence as Intelligence, WorkspaceRecommendation } from "@/types";

/**
 * Workspace Intelligence (Phase 3 #4) — what's actually going on in this
 * workspace, read by the AI from the workspace's own signals (projects, tasks,
 * approvals, AI work, memory, Brand Brain). The Executive Dashboard shows the
 * numbers; this says what they mean and what to do about it.
 *
 * Recommendations aren't advice you have to re-type: each one hands off to the
 * Work Queue, which plans and runs it — with the same approval gate on anything
 * with real-world consequences. Mobile-first, one thumb-reachable column.
 */
export default function WorkspaceIntelligencePage() {
  const { activeCompany, activeCompanyId } = useCompany();
  const toast = useToast();
  const navigate = useNavigate();
  const [data, setData] = useState<Intelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dispatching, setDispatching] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      if (!activeCompanyId) return;
      refresh ? setRefreshing(true) : setLoading(true);
      try {
        setData(await api.getWorkspaceIntelligence(activeCompanyId, refresh));
      } catch (err) {
        toast.push(err instanceof ApiError ? err.message : "Couldn't read this workspace.", "error");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [activeCompanyId, toast]
  );

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  /** Hand a recommendation to the Work Queue, which plans and runs it. */
  async function dispatchToWorkQueue(rec: WorkspaceRecommendation) {
    if (!activeCompanyId || dispatching) return;
    setDispatching(rec.title);
    try {
      const run = await api.createWorkPlan(`${rec.title}. Context: ${rec.why}`, activeCompanyId);
      navigate(`/company/work-queue?run=${run.id}&autorun=1`);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't start that work.", "error");
      setDispatching(null);
    }
  }

  if (!activeCompanyId) {
    return (
      <main className="flex h-full flex-1 items-center justify-center p-6 text-center text-sm text-jarvis-muted">
        Select a workspace to see its intelligence.
      </main>
    );
  }

  const ev = data?.evidence;

  return (
    // Block flow, not a flex column: in a scrolling flex column the sections
    // shrink to fit instead of scrolling, and hud-panel's overflow:hidden then
    // clips their text.
    <main className="h-full min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
      <ModulePageHeader
        icon={BrainCircuit}
        title="Workspace Intelligence"
        description={`What's actually happening in ${activeCompany?.name ?? "this workspace"} — read from its own projects, tasks, approvals, AI work, memory, and Brand Brain.`}
        sampleData={false}
      />

      {loading && !data ? (
        <div className="hud-panel hud-corner shrink-0 space-y-3 p-4">
          <div className="skeleton h-5 w-3/4 rounded" />
          <div className="skeleton h-3 w-full rounded" />
          <div className="skeleton h-3 w-5/6 rounded" />
        </div>
      ) : (
        data && (
          <>
            {/* The reading */}
            <section className="hud-panel hud-corner shrink-0 p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 flex-1 font-display text-base font-semibold leading-snug text-jarvis-text">
                  {data.headline}
                </p>
                <button
                  onClick={() => load(true)}
                  disabled={refreshing}
                  aria-label="Re-read this workspace"
                  className="press-scale shrink-0 rounded-lg p-2 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                >
                  <RefreshCw className={refreshing ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                </button>
              </div>
              {data.state_of_play && (
                <p className="mt-2 whitespace-pre-wrap text-sm text-jarvis-muted">{data.state_of_play}</p>
              )}
            </section>

            {/* What Jarvis is reading it from — the evidence, so the analysis
                is auditable rather than a black box. */}
            {ev && (
              <section className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label="Active projects" value={`${ev.projects.active}/${ev.projects.total}`} />
                <Stat label="Open tasks" value={`${ev.tasks.total - (ev.tasks.by_status.done ?? 0)}`} />
                <Stat label="Pending approvals" value={`${ev.pending_approvals.length}`} tone={ev.pending_approvals.length ? "amber" : undefined} />
                <Stat
                  label="Brand Brain"
                  value={ev.brand_brain.connected ? `${ev.brand_brain.products} products` : "Not connected"}
                />
              </section>
            )}

            {data.signals.length > 0 && (
              <section className="hud-panel hud-corner shrink-0 p-4">
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-jarvis-faint">
                  Signals
                </h2>
                <ul className="space-y-2">
                  {data.signals.map((s, i) => (
                    <li key={i} className="text-sm">
                      <span className="font-medium text-jarvis-text">{s.label}</span>
                      <span className="text-jarvis-muted"> — {s.detail}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {data.risks.length > 0 && (
              <section className="hud-panel hud-corner shrink-0 p-4">
                <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-jarvis-amber">
                  <AlertTriangle className="h-3.5 w-3.5" /> Risks
                </h2>
                <ul className="space-y-2.5">
                  {data.risks.map((r, i) => (
                    <li key={i}>
                      <p className="text-sm font-medium text-jarvis-text">{r.title}</p>
                      <p className="text-xs text-jarvis-muted">{r.detail}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {data.recommendations.length > 0 && (
              <section className="hud-panel hud-corner shrink-0 p-4">
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-jarvis-faint">
                  Do next
                </h2>
                <ul className="space-y-2.5">
                  {data.recommendations.map((r, i) => (
                    <li
                      key={i}
                      className="rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 p-3"
                    >
                      <p className="text-sm font-medium text-jarvis-text">{r.title}</p>
                      <p className="mt-0.5 text-xs text-jarvis-muted">{r.why}</p>
                      <div className="mt-2 flex items-center gap-2">
                        <button
                          onClick={() => dispatchToWorkQueue(r)}
                          disabled={!!dispatching}
                          className="press-scale flex items-center gap-1.5 rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-2.5 py-1.5 text-[11px] font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
                        >
                          {dispatching === r.title ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                          Send to Work Queue
                        </button>
                        {r.real_world && (
                          <span className="flex items-center gap-1 rounded bg-jarvis-amber/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-jarvis-amber">
                            <ShieldCheck className="h-3 w-3" /> needs approval
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {!data.risks.length && !data.recommendations.length && !data.signals.length && (
              <p className="flex items-center gap-2 px-1 text-sm text-jarvis-muted">
                <Sparkles className="h-4 w-4 shrink-0" />
                Not enough activity in this workspace yet to read anything meaningful.
              </p>
            )}
          </>
        )
      )}
    </main>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "amber" }) {
  return (
    <div className="hud-panel rounded-xl p-3">
      <p className="text-[10px] uppercase tracking-widest text-jarvis-faint">{label}</p>
      <p className={`mt-1 font-data text-sm ${tone === "amber" ? "text-jarvis-amber" : "text-jarvis-text"}`}>
        {value}
      </p>
    </div>
  );
}
