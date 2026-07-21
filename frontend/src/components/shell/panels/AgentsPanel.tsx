import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, Play, Loader2 } from "lucide-react";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import PanelFrame, { PanelEmpty, PanelError, PanelLoading } from "@/components/shell/panels/PanelFrame";
import type { Agent, AgentRun, AgentRunStatus } from "@/types";

const STATUS_STYLES: Record<AgentRunStatus, string> = {
  queued: "text-jarvis-muted border-jarvis-border bg-jarvis-panel2/40",
  running: "text-jarvis-amber border-jarvis-amber/40 bg-jarvis-amber/10",
  awaiting_approval: "text-jarvis-amber border-jarvis-amber/40 bg-jarvis-amber/10",
  completed: "text-jarvis-emerald border-jarvis-emerald/40 bg-jarvis-emerald/10",
  failed: "text-jarvis-rose border-jarvis-rose/40 bg-jarvis-rose/10",
};

const ACTIVE: AgentRunStatus[] = ["queued", "running", "awaiting_approval"];

// Active Agents — the AI executives that operate within the active company.
// Lists the roster + recent runs and launches a run for the active workspace
// via the existing /agents endpoints. Polls while any run is active.
export default function AgentsPanel({ onClose }: { onClose: () => void }) {
  const { activeCompanyId, activeCompany } = useCompany();
  const toast = useToast();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [launchKey, setLaunchKey] = useState<string>("");
  const [objective, setObjective] = useState("");
  const [launching, setLaunching] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const [roster, runList] = await Promise.all([
        api.listAgents(),
        api.listAgentRuns({ companyId: activeCompanyId ?? "none" }),
      ]);
      setAgents(roster);
      setRuns(runList);
      setLaunchKey((k) => k || roster[0]?.key || "");
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [activeCompanyId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while a run is active so status/result update live.
  const hasActive = useMemo(() => runs.some((r) => ACTIVE.includes(r.status)), [runs]);
  useEffect(() => {
    if (!hasActive) return;
    const t = setInterval(async () => {
      try {
        setRuns(await api.listAgentRuns({ companyId: activeCompanyId ?? "none" }));
      } catch {
        /* ignore poll errors */
      }
    }, 4000);
    return () => clearInterval(t);
  }, [hasActive, activeCompanyId]);

  async function launch() {
    if (!launchKey || !objective.trim()) return;
    setLaunching(true);
    try {
      await api.runAgent(launchKey, { objective: objective.trim(), company_id: activeCompanyId });
      setObjective("");
      toast.push("Agent launched.", "success");
      await load();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to launch agent.", "error");
    } finally {
      setLaunching(false);
    }
  }

  return (
    <PanelFrame
      title="Active Agents"
      icon={Bot}
      onClose={onClose}
      onRefresh={load}
      refreshing={loading}
      subtitle={activeCompany?.name ?? "No active company"}
    >
      {failed && agents.length === 0 ? (
        <PanelError onRetry={load} />
      ) : (
      <>
      {/* Launch */}
      <div className="mb-4 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/30 p-3">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-jarvis-muted">
          Launch an agent
        </p>
        <select
          value={launchKey}
          onChange={(e) => setLaunchKey(e.target.value)}
          className="mb-2 w-full rounded-lg border border-jarvis-border bg-jarvis-panel2/60 px-2.5 py-1.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
        >
          {agents.map((a) => (
            <option key={a.key} value={a.key}>
              {a.label}
            </option>
          ))}
        </select>
        <textarea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="Objective for the agent…"
          rows={2}
          className="mb-2 w-full resize-none rounded-lg border border-jarvis-border bg-jarvis-panel2/60 px-2.5 py-1.5 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
        />
        <button
          onClick={launch}
          disabled={launching || !launchKey || !objective.trim()}
          className="press-scale flex w-full items-center justify-center gap-2 rounded-lg border border-jarvis-cyan/30 bg-jarvis-cyan/10 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
        >
          {launching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          Launch
        </button>
      </div>

      {/* Runs */}
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-jarvis-muted">Runs</p>
      {loading ? (
        <PanelLoading />
      ) : runs.length === 0 ? (
        <PanelEmpty label="No agent runs yet." />
      ) : (
        <ul className="space-y-2">
          {runs.map((r) => (
            <li key={r.id} className="rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-jarvis-text">
                  {r.agent_label}
                </span>
                <span
                  className={clsx(
                    "shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                    STATUS_STYLES[r.status]
                  )}
                >
                  {r.status.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-jarvis-muted">{r.objective}</p>
            </li>
          ))}
        </ul>
      )}
      </>
      )}
    </PanelFrame>
  );
}
