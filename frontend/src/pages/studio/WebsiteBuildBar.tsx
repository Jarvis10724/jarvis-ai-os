import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  AlertTriangle,
  Check,
  Globe,
  Hammer,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";

import { api, ApiError, streamWebsiteBuild, type WebsiteBuildStage } from "@/api/client";
import type { Client } from "@/types";

type Phase = "idle" | "analyzing" | "planning" | "awaiting_approval" | "generating" | "done" | "error";
type Mode = "new" | "improve" | "client";

const STAGE_ORDER = ["analyze", "plan", "images", "components", "preview"];

interface SessionInfo {
  id: string;
  mode?: string | null;
  source_url?: string | null;
  client_id?: string | null;
}

/**
 * Build a Website control with the three modes:
 *  - New: build a fresh site for the active company.
 *  - Improve Existing: crawl a URL and produce an improved site.
 *  - Client: build under a selected/created Client, kept separate.
 * Picking a mode different from the current session (or new params) spins up a
 * fresh, correctly-scoped session+project before building. Streams live
 * progress and gates the major generation behind approval.
 */
export default function WebsiteBuildBar({
  session,
  companyId,
  onCreateModeSession,
  onRefresh,
  onFocusStage,
  disabled,
}: {
  session: SessionInfo;
  companyId: string | null;
  onCreateModeSession: (opts: { mode: Mode; source_url?: string; client_id?: string }) => Promise<string | null>;
  onRefresh: (sessionId: string) => void;
  /** Point the workspace panel at a stage's state_key (follow the build). */
  onFocusStage?: (stateKey: string) => void;
  disabled?: boolean;
}) {
  const [mode, setMode] = useState<Mode>((session.mode as Mode) || "new");
  const [url, setUrl] = useState(session.source_url || "");
  const [clientId, setClientId] = useState(session.client_id || "");
  const [clients, setClients] = useState<Client[]>([]);
  const [newClientName, setNewClientName] = useState("");
  const [showNewClient, setShowNewClient] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [stages, setStages] = useState<Record<string, WebsiteBuildStage>>({});
  const [approval, setApproval] = useState<{ summary: string; major_actions: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const buildIdRef = useRef<string>(session.id);
  // True while WE are creating a session mid-build, so the session.id change we
  // triggered doesn't reset/abort the in-flight build.
  const selfCreatedRef = useRef(false);

  // Reset build UI + re-sync selectors when the active session changes — unless
  // the change was our own (a mode session we just created to build into).
  useEffect(() => {
    if (selfCreatedRef.current) {
      selfCreatedRef.current = false;
      buildIdRef.current = session.id;
      return;
    }
    abortRef.current?.();
    abortRef.current = null;
    setPhase("idle");
    setStages({});
    setApproval(null);
    setError(null);
    setMode((session.mode as Mode) || "new");
    setUrl(session.source_url || "");
    setClientId(session.client_id || "");
    buildIdRef.current = session.id;
  }, [session.id]);
  useEffect(() => () => abortRef.current?.(), []);

  // Load clients for the active company (for Client mode).
  useEffect(() => {
    api
      .listClients(companyId ?? "none")
      .then(setClients)
      .catch(() => setClients([]));
  }, [companyId]);

  async function createClientInline(): Promise<string | null> {
    const name = newClientName.trim();
    if (!name) return null;
    try {
      const c = await api.createClient({ name, company_id: companyId });
      setClients((prev) => [c, ...prev]);
      setClientId(c.id);
      setNewClientName("");
      setShowNewClient(false);
      return c.id;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create client.");
      return null;
    }
  }

  function validate(): string | null {
    if (mode === "improve" && !url.trim()) return "Enter the URL of the existing website.";
    if (mode === "client" && !clientId) return "Select or create a client first.";
    return null;
  }

  // True when the selected mode/params differ from the current session, so a
  // fresh mode-scoped session must be created before building.
  function needsNewSession(): boolean {
    const curMode = (session.mode as Mode) || "new";
    if (mode !== curMode) return true;
    if (mode === "improve" && url.trim() !== (session.source_url || "")) return true;
    if (mode === "client" && clientId !== (session.client_id || "")) return true;
    return false;
  }

  async function run(approved: boolean) {
    const v = validate();
    if (v) {
      setError(v);
      setPhase("error");
      return;
    }
    setError(null);
    setApproval(null);
    setStages({});

    // On the initial (plan) run, resolve the session we build into.
    if (!approved) {
      if (needsNewSession()) {
        setPhase(mode === "improve" ? "analyzing" : "planning");
        selfCreatedRef.current = true; // suppress the reset from the id change we cause
        const newId = await onCreateModeSession({
          mode,
          source_url: mode === "improve" ? url.trim() : undefined,
          client_id: mode === "client" ? clientId : undefined,
        });
        if (!newId) {
          selfCreatedRef.current = false;
          setError("Couldn't start the build session.");
          setPhase("error");
          return;
        }
        buildIdRef.current = newId;
      } else {
        buildIdRef.current = session.id;
      }
    }

    setPhase(approved ? "generating" : mode === "improve" ? "analyzing" : "planning");
    abortRef.current = streamWebsiteBuild(
      buildIdRef.current,
      { approved, brief: null },
      {
        onStage: (s) => {
          setStages((prev) => ({ ...prev, [s.stage]: s }));
          if (s.status === "done") onRefresh(buildIdRef.current);
        },
        onAwaitingApproval: (p) => {
          setApproval(p);
          setPhase("awaiting_approval");
          abortRef.current = null;
          onRefresh(buildIdRef.current);
          onFocusStage?.("sitemap"); // surface the plan being approved
        },
        onDone: (p) => {
          abortRef.current = null;
          onRefresh(buildIdRef.current);
          if (p.phase === "build") {
            setPhase("done");
            onFocusStage?.("preview_html"); // land on the finished site
          }
        },
        onError: (msg) => {
          setError(msg);
          setPhase("error");
          abortRef.current = null;
        },
      }
    );
  }

  const running = phase === "planning" || phase === "generating" || phase === "analyzing";
  const orderedStages = STAGE_ORDER.map((k) => stages[k]).filter(Boolean) as WebsiteBuildStage[];
  const MODES: { key: Mode; label: string; icon: typeof Globe }[] = [
    { key: "new", label: "New", icon: Hammer },
    { key: "improve", label: "Improve Existing", icon: RefreshCw },
    { key: "client", label: "Client", icon: Users },
  ];

  return (
    <div className="border-b border-jarvis-border/60 bg-jarvis-panel/30 px-5 py-3">
      {/* Mode selector */}
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        {MODES.map((m) => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            disabled={running}
            className={clsx(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition disabled:opacity-50",
              mode === m.key
                ? "border-jarvis-cyan/50 bg-jarvis-cyan/15 text-jarvis-cyan"
                : "border-jarvis-border text-jarvis-muted hover:text-jarvis-text"
            )}
          >
            <m.icon className="h-3.5 w-3.5" />
            {m.label}
          </button>
        ))}
      </div>

      {/* Mode-specific inputs */}
      {mode === "improve" && (
        <div className="mb-2 flex items-center gap-1.5">
          <Globe className="h-3.5 w-3.5 shrink-0 text-jarvis-muted" />
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={running}
            placeholder="Existing website URL to analyze & improve (e.g. acme.com)"
            className="min-w-0 flex-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-xs text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
          />
        </div>
      )}
      {mode === "client" && (
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          <Users className="h-3.5 w-3.5 shrink-0 text-jarvis-muted" />
          {showNewClient ? (
            <>
              <input
                value={newClientName}
                onChange={(e) => setNewClientName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createClientInline()}
                autoFocus
                placeholder="New client name"
                className="min-w-0 flex-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-xs text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
              />
              <button
                onClick={createClientInline}
                className="press-scale rounded-lg border border-jarvis-emerald/40 bg-jarvis-emerald/10 px-2.5 py-2 text-[11px] font-semibold text-jarvis-emerald"
              >
                Create
              </button>
              <button onClick={() => setShowNewClient(false)} className="px-2 py-2 text-[11px] text-jarvis-muted">
                Cancel
              </button>
            </>
          ) : (
            <>
              <select
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                disabled={running}
                className="min-w-0 flex-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-xs text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
              >
                <option value="">Select a client…</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.project_count})
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowNewClient(true)}
                className="press-scale flex items-center gap-1 rounded-lg border border-jarvis-border px-2.5 py-2 text-[11px] font-semibold text-jarvis-muted hover:text-jarvis-cyan"
              >
                <Plus className="h-3.5 w-3.5" /> New client
              </button>
            </>
          )}
        </div>
      )}

      {/* Build button */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => run(false)}
          disabled={running || disabled}
          className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3.5 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
        >
          {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Hammer className="h-3.5 w-3.5" />}
          {mode === "improve" ? "Analyze & Build" : mode === "client" ? "Build for Client" : "Build Website"}
        </button>
        <span className="text-[10px] text-jarvis-faint">
          {mode === "new" && "Fresh site for the active company."}
          {mode === "improve" && "Crawls the site, preserves branding, rebuilds it better."}
          {mode === "client" && "Saved as a separate project under the client."}
        </span>
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
              {s.detail && <span className="truncate text-jarvis-faint">· {s.detail}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Approval gate */}
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
