import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, Check, Hammer, Loader2, ShieldCheck, Sparkles, X } from "lucide-react";

import { streamWebsiteBuild, type WebsiteBuildStage } from "@/api/client";

type Phase = "idle" | "planning" | "awaiting_approval" | "generating" | "done" | "error";

const STAGE_ORDER = ["plan", "images", "components", "preview"];

/**
 * Drives the Build a Website pipeline: a single "Build Website" button plans the
 * site (live progress), then presents an approval gate before the major action
 * (images + React components + preview). Refreshes the workspace panels as each
 * stage completes. Self-contained so Studio stays generic.
 */
export default function WebsiteBuildBar({
  sessionId,
  onRefresh,
  disabled,
}: {
  sessionId: string;
  onRefresh: () => void;
  disabled?: boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [brief, setBrief] = useState("");
  const [stages, setStages] = useState<Record<string, WebsiteBuildStage>>({});
  const [approval, setApproval] = useState<{ summary: string; major_actions: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  // Reset when switching sessions; cancel any in-flight build.
  useEffect(() => {
    abortRef.current?.();
    abortRef.current = null;
    setPhase("idle");
    setStages({});
    setApproval(null);
    setError(null);
  }, [sessionId]);
  useEffect(() => () => abortRef.current?.(), []);

  function run(approved: boolean) {
    setError(null);
    setApproval(null);
    setStages({});
    setPhase(approved ? "generating" : "planning");
    abortRef.current = streamWebsiteBuild(
      sessionId,
      { approved, brief: brief.trim() || null },
      {
        onStage: (s) => {
          setStages((prev) => ({ ...prev, [s.stage]: s }));
          if (s.status === "done") onRefresh();
        },
        onAwaitingApproval: (p) => {
          setApproval(p);
          setPhase("awaiting_approval");
          abortRef.current = null;
          onRefresh();
        },
        onDone: (p) => {
          abortRef.current = null;
          onRefresh();
          // Only the approved build finalizes; a plan-phase done must not
          // override the approval gate.
          if (p.phase === "build") setPhase("done");
        },
        onError: (msg) => {
          setError(msg);
          setPhase("error");
          abortRef.current = null;
        },
      }
    );
  }

  const running = phase === "planning" || phase === "generating";
  const orderedStages = STAGE_ORDER.map((k) => stages[k]).filter(Boolean) as WebsiteBuildStage[];

  return (
    <div className="border-b border-jarvis-border/60 bg-jarvis-panel/30 px-5 py-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => run(false)}
          disabled={running || disabled}
          className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3.5 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
        >
          {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Hammer className="h-3.5 w-3.5" />}
          {phase === "idle" || phase === "error" ? "Build Website" : "Re-plan"}
        </button>
        <input
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          disabled={running}
          placeholder="Optional: describe the site (or leave blank to use the conversation)…"
          className="min-w-0 flex-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-xs text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
        />
      </div>

      {/* Live progress */}
      {orderedStages.length > 0 && (
        <div className="mt-2.5 space-y-1">
          {orderedStages.map((s) => (
            <div key={s.stage} className="flex items-center gap-2 text-xs">
              {s.status === "running" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-jarvis-cyan" />
              ) : s.status === "error" ? (
                <X className="h-3.5 w-3.5 text-jarvis-rose" />
              ) : (
                <Check className="h-3.5 w-3.5 text-jarvis-emerald" />
              )}
              <span className="text-jarvis-text">{s.label}</span>
              {s.detail && <span className="text-jarvis-faint">· {s.detail}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Approval gate before the major action */}
      {phase === "awaiting_approval" && approval && (
        <div className="mt-3 rounded-xl border border-jarvis-amber/40 bg-jarvis-amber/10 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-jarvis-amber">
            <ShieldCheck className="h-4 w-4" />
            Approval required before the major build
          </div>
          <p className="mb-2 text-xs text-jarvis-text">{approval.summary}</p>
          <ul className="mb-2.5 space-y-0.5">
            {approval.major_actions.map((a, i) => (
              <li key={i} className="flex items-center gap-1.5 text-[11px] text-jarvis-muted">
                <Sparkles className="h-3 w-3 text-jarvis-amber" /> {a}
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2">
            <button
              onClick={() => run(true)}
              className="press-scale flex items-center gap-1.5 rounded-lg border border-jarvis-emerald/40 bg-jarvis-emerald/10 px-3 py-1.5 text-xs font-semibold text-jarvis-emerald transition hover:bg-jarvis-emerald/20"
            >
              <Check className="h-3.5 w-3.5" /> Approve & generate
            </button>
            <button
              onClick={() => {
                setPhase("idle");
                setApproval(null);
              }}
              className="rounded-lg px-3 py-1.5 text-xs text-jarvis-muted transition hover:text-jarvis-text"
            >
              Not now
            </button>
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-jarvis-emerald">
          <Check className="h-3.5 w-3.5" /> Build complete — see the Components, Images, and Preview panels.
        </div>
      )}

      {phase === "error" && error && (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-lg border border-jarvis-rose/30 bg-jarvis-rose/10 px-3 py-2 text-xs text-jarvis-rose">
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5" /> {error}
          </span>
          <button onClick={() => run(false)} className="font-semibold underline">
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
