import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, CircleDashed, ListChecks, Loader2, Play, ShieldCheck, Sparkles } from "lucide-react";

import { api, ApiError, streamWork, type WorkEvent } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import type { WorkRun, WorkSubtask } from "@/types";

const STATE_META: Record<
  WorkSubtask["status"],
  { label: string; className: string; icon: typeof Check }
> = {
  planned: { label: "Planned", className: "text-jarvis-muted", icon: CircleDashed },
  working: { label: "Working", className: "text-jarvis-cyan", icon: Loader2 },
  waiting_approval: { label: "Waiting for approval", className: "text-jarvis-amber", icon: ShieldCheck },
  complete: { label: "Complete", className: "text-jarvis-emerald", icon: Check },
};

/**
 * Autonomous Work Queue (Phase 3) — give Jarvis a large request; it breaks it
 * into subtasks and works through them live, tracking each Planned → Working →
 * Waiting for Approval → Complete. Approval-gated: real-world steps stop for a
 * human. Mobile-first; the whole thing is one thumb-reachable column.
 */
export default function WorkQueuePage() {
  const { activeCompany, activeCompanyId } = useCompany();
  const toast = useToast();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [run, setRun] = useState<WorkRun | null>(null);
  const [planning, setPlanning] = useState(false);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => () => abortRef.current?.(), []);

  async function plan() {
    const request = input.trim();
    if (!request || planning) return;
    setPlanning(true);
    setRun(null);
    try {
      setRun(await api.createWorkPlan(request, activeCompanyId));
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't plan the work.", "error");
    } finally {
      setPlanning(false);
    }
  }

  const applyEvent = useCallback((e: WorkEvent) => {
    setRun((cur) => {
      if (!cur) return cur;
      if (e.type === "run") return { ...cur, status: e.status ?? "running" };
      if (e.type === "done") return { ...cur, status: e.status ?? cur.status };
      if (e.type === "subtask" && e.id) {
        return {
          ...cur,
          subtasks: cur.subtasks.map((s) =>
            s.id === e.id
              ? { ...s, status: (e.status as WorkSubtask["status"]) ?? s.status, result: e.result ?? s.result, approval_id: e.approval_id ?? s.approval_id }
              : s
          ),
        };
      }
      return cur;
    });
  }, []);

  function start() {
    if (!run || running) return;
    setRunning(true);
    abortRef.current = streamWork(run.id, {
      onEvent: applyEvent,
      onDone: async () => {
        setRunning(false);
        // Pull final results (subtask work products) once the stream ends.
        try {
          setRun(await api.getWorkRun(run.id));
        } catch {
          /* keep streamed state */
        }
      },
      onError: (msg) => {
        setRunning(false);
        toast.push(msg, "error");
      },
    });
  }

  if (!activeCompanyId) {
    return (
      <main className="flex h-full flex-1 items-center justify-center p-6 text-center text-sm text-jarvis-muted">
        Select a workspace to use the Work Queue.
      </main>
    );
  }

  const done = run && (run.status === "completed" || run.status === "waiting");

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <ModulePageHeader
        icon={ListChecks}
        title="Work Queue"
        description={`Give Jarvis a goal for ${activeCompany?.name ?? "this workspace"} — it plans the steps, does the work, and stops for your approval on anything with real-world consequences.`}
        sampleData={false}
      />

      {/* Request input */}
      <div className="hud-panel hud-corner p-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={2}
          placeholder="e.g. Plan a spring launch for the Copper collection and email the supplier a reorder"
          className="w-full resize-none rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-[color:var(--ws-accent-soft)] focus:outline-none"
        />
        <div className="mt-2 flex justify-end">
          <button
            onClick={plan}
            disabled={!input.trim() || planning}
            className="press-scale flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-jarvis-bg transition disabled:opacity-40"
            style={{ backgroundColor: "var(--ws-accent)" }}
          >
            {planning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {planning ? "Planning…" : "Plan the work"}
          </button>
        </div>
      </div>

      {/* The plan + live execution */}
      {run && (
        <div className="hud-panel hud-corner flex flex-col gap-3 p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="min-w-0 flex-1 truncate text-sm font-semibold text-jarvis-text">{run.objective}</p>
            {run.status === "planned" && (
              <button
                onClick={start}
                disabled={running}
                className="press-scale flex shrink-0 items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-1.5 text-xs font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
              >
                <Play className="h-3.5 w-3.5" /> Run
              </button>
            )}
            {running && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-jarvis-cyan" />}
          </div>

          <ol className="space-y-2">
            {run.subtasks.map((s, i) => {
              const meta = STATE_META[s.status];
              const Icon = meta.icon;
              return (
                <li key={s.id} className="rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 p-3">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-jarvis-panel3/50 text-[10px] font-bold text-jarvis-muted">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-jarvis-text">{s.title}</p>
                      <div className={`mt-1 flex items-center gap-1.5 text-[11px] font-medium ${meta.className}`}>
                        <Icon className={s.status === "working" ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
                        {meta.label}
                        {s.real_world && s.status !== "complete" && (
                          <span className="rounded bg-jarvis-amber/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-jarvis-amber">
                            real-world
                          </span>
                        )}
                      </div>
                      {s.status === "complete" && s.result && (
                        <p className="mt-1.5 whitespace-pre-wrap rounded-lg bg-jarvis-panel/40 p-2 text-[11px] text-jarvis-muted">
                          {s.result}
                        </p>
                      )}
                      {s.status === "waiting_approval" && (
                        <button
                          onClick={() => navigate("/approvals")}
                          className="mt-1.5 text-[11px] font-semibold text-jarvis-amber underline-offset-2 hover:underline"
                        >
                          Review in Approvals →
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>

          {done && (
            <p className="text-xs text-jarvis-muted">
              {run.status === "waiting"
                ? "Some steps are waiting for your approval."
                : "All steps complete."}
            </p>
          )}
        </div>
      )}
    </main>
  );
}
