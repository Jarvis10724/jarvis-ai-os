import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import {
  Archive,
  ArchiveRestore,
  Bot,
  Check,
  Clock3,
  CornerDownLeft,
  FileText,
  History,
  Layers,
  ListChecks,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  User,
  X,
} from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import { api, ApiError, streamWorkspaceMessage } from "@/api/client";
import MarkdownLite from "@/components/MarkdownLite";
import { useCompany } from "@/context/CompanyContext";
import { useProject } from "@/context/ProjectContext";
import { useToast } from "@/context/ToastContext";
import { QUICK_ACTIONS } from "@/lib/quickActions";
import { AutomationBanner, StagePanel, stageHasValue, type PanelCtx } from "@/pages/studio/panels";
import WebsiteBuildBar from "@/pages/studio/WebsiteBuildBar";
import type { WorkspaceDetail, WorkspaceSummary } from "@/types";

function lastSessionKey(action: string, companyId: string | null): string {
  return `jarvis_ws_last_${action}_${companyId ?? "none"}`;
}
const GLOBAL_LAST_KEY = "jarvis_ws_global_last";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const TASK_TONE: Record<string, string> = {
  backlog: "text-jarvis-muted",
  in_progress: "text-jarvis-amber",
  review: "text-jarvis-cyan",
  done: "text-jarvis-emerald",
};

type SaveState = "idle" | "streaming" | "saved" | "error";
type RightTab = "workspace" | "deliverables" | "tasks";

export default function StudioPage() {
  const { action = "" } = useParams();
  const meta = QUICK_ACTIONS.find((a) => a.pluginName === action);
  const { activeCompany, activeCompanyId } = useCompany();
  const { activeProjectId } = useProject();
  const toast = useToast();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState<WorkspaceSummary[]>([]);
  const [recent, setRecent] = useState<WorkspaceSummary[]>([]);
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [rightTab, setRightTab] = useState<RightTab>("workspace");
  // Mobile-only: below xl the sessions rail + workspace panel are collapsed, so
  // this toggles the center column between the conversation and the workspace
  // panel (which holds the Website Builder preview + deliverables + tasks).
  const [mobileView, setMobileView] = useState<"chat" | "panel">("chat");
  // Mobile-only: the sessions rail is hidden below md, so this dropdown lets you
  // switch sessions / start a new one from the header on a phone.
  const [showMobileSessions, setShowMobileSessions] = useState(false);
  const [activeStage, setActiveStage] = useState<string>("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [showRecent, setShowRecent] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [imageConfigured, setImageConfigured] = useState(false);
  const [generatingImageFor, setGeneratingImageFor] = useState<string | null>(null);
  const [lastAttempt, setLastAttempt] = useState<{ content: string; stage: string } | null>(null);

  const abortRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const companyKey = activeCompanyId ?? "none";

  // Whether real image generation is available (Logo Studio uses this).
  useEffect(() => {
    api.workspaceImageStatus().then((s) => setImageConfigured(s.configured)).catch(() => {});
  }, []);

  const openSession = useCallback(async (id: string) => {
    setLoadingDetail(true);
    try {
      const d = await api.getWorkspace(id);
      setDetail(d);
      setSavedAt(d.updated_at);
      setSaveState(d.messages.length ? "saved" : "idle");
      localStorage.setItem(lastSessionKey(action, activeCompanyId), id);
      localStorage.setItem(GLOBAL_LAST_KEY, JSON.stringify({ action, id }));
    } catch {
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, companyKey]);

  // Load this action's sessions for the active company, then restore the last
  // opened one (or the most recent). Re-runs when the workspace type or the
  // active company changes — switching companies re-scopes without losing the
  // other company's state (it's all server-persisted).
  useEffect(() => {
    if (!meta) return;
    let cancelled = false;
    setLoadingList(true);
    setDetail(null);
    Promise.all([
      api.listWorkspaces({ companyId: activeCompanyId ?? "none", action, status: "active" }),
      api.recentWorkspaces({ companyId: activeCompanyId ?? "none" }).catch(() => []),
    ])
      .then(([list, rec]) => {
        if (cancelled) return;
        setSessions(list);
        setRecent(rec);
        const remembered = localStorage.getItem(lastSessionKey(action, activeCompanyId));
        const toOpen = list.find((s) => s.id === remembered) ?? list[0];
        if (toOpen) openSession(toOpen.id);
      })
      .catch(() => !cancelled && setSessions([]))
      .finally(() => !cancelled && setLoadingList(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, companyKey, meta]);

  // When a different session is opened, restore the panel to the furthest-along
  // stage that already has content (e.g. Preview after a completed build) rather
  // than the empty first stage — so reopening a finished website shows the work,
  // not a blank Requirements panel. Keyed on session id so it only fires on an
  // actual session switch, never while the user is manually navigating stages.
  useEffect(() => {
    const stages = detail?.config?.stages ?? [];
    if (!stages.length) return;
    if (stages.some((s) => s.state_key === activeStage)) return; // keep valid selection
    const state = detail?.state ?? {};
    const populated = [...stages].reverse().find((s) => stageHasValue(state, s.state_key));
    setActiveStage((populated ?? stages[0]).state_key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.id]);

  // Cancel any in-flight stream on unmount / switching away.
  useEffect(() => () => abortRef.current?.(), []);

  useEffect(() => {
    requestAnimationFrame(() =>
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
    );
  }, [detail?.messages.length, streamText]);

  if (!meta) return <Navigate to="/" replace />;

  async function refreshLists() {
    const [list, rec] = await Promise.all([
      api.listWorkspaces({ companyId: activeCompanyId ?? "none", action, status: "active" }),
      api.recentWorkspaces({ companyId: activeCompanyId ?? "none" }).catch(() => []),
    ]);
    setSessions(list);
    setRecent(rec);
  }

  async function newSession(opts?: {
    mode?: "new" | "improve" | "client";
    source_url?: string;
    client_id?: string;
  }): Promise<WorkspaceDetail | null> {
    try {
      // Attach to the active shared Project (client mode resolves its own
      // client project server-side, so don't force the active one there).
      const created = await api.createWorkspace({
        action,
        company_id: activeCompanyId,
        project_id: opts?.mode === "client" ? null : activeProjectId,
        ...opts,
      });
      setSessions((prev) => [{ ...created }, ...prev]);
      setDetail(created);
      setSaveState("idle");
      setActiveStage(created.config?.stages[0]?.state_key ?? "");
      localStorage.setItem(lastSessionKey(action, activeCompanyId), created.id);
      localStorage.setItem(GLOBAL_LAST_KEY, JSON.stringify({ action, id: created.id }));
      return created;
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't create the session.", "error");
      return null;
    }
  }

  async function sendMessage(rawContent: string, stage: string) {
    const content = rawContent.trim();
    if (!content || streaming) return;

    let session = detail;
    if (!session) {
      session = await newSession();
      if (!session) return;
    }

    setLastAttempt({ content, stage });
    setDetail((d) => (d ? { ...d, messages: [...d.messages, { role: "user", content }] } : d));
    setInput("");
    setStreamText("");
    setStreaming(true);
    setSaveState("streaming");

    abortRef.current = streamWorkspaceMessage(
      session.id,
      content,
      {
        onToken: (t) => setStreamText((prev) => prev + t),
        onDone: async () => {
          setStreaming(false);
          setStreamText("");
          abortRef.current = null;
          setSaveState("saved");
          setSavedAt(new Date().toISOString());
          setLastAttempt(null);
          // Refetch so messages/artifacts/state/tasks reflect what was saved.
          await openSession(session!.id);
          refreshLists().catch(() => {});
        },
        onError: (msg) => {
          setStreaming(false);
          setStreamText("");
          abortRef.current = null;
          setSaveState("error");
          toast.push(msg, "error");
        },
      },
      stage || undefined
    );
  }

  function retryLast() {
    if (lastAttempt) sendMessage(lastAttempt.content, lastAttempt.stage);
  }

  async function generateImage(conceptId: string | null, name: string, prompt: string) {
    if (!detail) return;
    setGeneratingImageFor(conceptId ?? name);
    try {
      const res = await api.generateWorkspaceImage(detail.id, { prompt, concept_id: conceptId, name });
      if (!res.configured) {
        toast.push(res.message ?? "Image generation isn't configured.", "info");
      } else {
        await openSession(detail.id);
        toast.push("Concept image generated.", "success");
      }
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Image generation failed.", "error");
    } finally {
      setGeneratingImageFor(null);
    }
  }

  async function removeSession(id: string) {
    try {
      await api.deleteWorkspace(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (detail?.id === id) setDetail(null);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't delete the session.", "error");
    }
  }

  async function setStatus(id: string, status: "active" | "archived") {
    try {
      await api.updateWorkspace(id, { status });
      if (status === "archived") {
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (detail?.id === id) setDetail((d) => (d ? { ...d, status } : d));
      }
      refreshLists().catch(() => {});
      toast.push(status === "archived" ? "Session archived." : "Session restored.", "success");
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't update the session.", "error");
    }
  }

  async function commitRename() {
    setRenaming(false);
    const title = renameValue.trim();
    if (!detail || !title || title === detail.title) return;
    try {
      const updated = await api.updateWorkspace(detail.id, { title });
      setDetail((d) => (d ? { ...d, title: updated.title } : d));
      setSessions((prev) => prev.map((s) => (s.id === detail.id ? { ...s, title: updated.title } : s)));
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't rename.", "error");
    }
  }

  function openRecent(s: WorkspaceSummary) {
    setShowRecent(false);
    localStorage.setItem(lastSessionKey(s.action, activeCompanyId), s.id);
    if (s.action === action) {
      openSession(s.id);
    } else {
      navigate(`/studio/${s.action}`);
    }
  }

  const Icon = meta.icon;
  const hasContent = detail && (detail.messages.length > 0 || streaming);
  const stages = detail?.config?.stages ?? [];
  const artifacts = detail?.artifacts ?? [];

  const panelCtx: PanelCtx | null = detail
    ? {
        actionKey: action,
        detail,
        imageConfigured,
        streaming,
        generatingImageFor,
        onPrompt: (stage, prompt) => sendMessage(prompt, stage),
        onGenerateImage: generateImage,
      }
    : null;

  // Version history: group artifacts by title, latest first.
  const versionGroups = useMemo(() => {
    const groups = new Map<string, typeof artifacts>();
    for (const a of artifacts) {
      const key = a.title;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(a);
    }
    return Array.from(groups.entries()).reverse();
  }, [artifacts]);

  return (
    <main className="relative flex h-full min-h-0 flex-1 overflow-hidden">
      {/* Sessions rail */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-jarvis-border/60 bg-jarvis-panel/40 md:flex">
        <div className="flex items-center gap-2.5 border-b border-jarvis-border/60 px-4 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10">
            <Icon className="h-4 w-4 text-jarvis-cyan" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-display text-sm font-bold tracking-wide text-jarvis-text">{meta.label}</p>
            <p className="truncate text-[10px] text-jarvis-muted">{activeCompany?.name ?? "No workspace"}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-3 pt-3">
          <button
            onClick={() => newSession()}
            className="press-scale flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
          >
            <Plus className="h-3.5 w-3.5" />
            New Session
          </button>
          <div className="relative">
            <button
              onClick={() => setShowRecent((v) => !v)}
              title="Recent sessions (all Quick Actions)"
              className="press-scale flex h-[34px] w-[34px] items-center justify-center rounded-xl border border-jarvis-border bg-jarvis-panel2/50 text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
            >
              <History className="h-4 w-4" />
            </button>
            {showRecent && (
              <div className="absolute right-0 top-10 z-30 w-64 rounded-xl border border-jarvis-border bg-jarvis-panel p-2 shadow-elevated-lg">
                <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-jarvis-faint">
                  Recent — all actions
                </p>
                {recent.length === 0 ? (
                  <p className="px-2 py-3 text-center text-xs text-jarvis-muted">Nothing recent.</p>
                ) : (
                  recent.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => openRecent(s)}
                      className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                    >
                      <span className="truncate flex-1">{s.title}</span>
                      <span className="shrink-0 text-[9px] text-jarvis-faint">{s.action_label}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          {loadingList ? (
            <div className="space-y-2 p-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-jarvis-muted">No sessions yet.</p>
          ) : (
            sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => openSession(s.id)}
                className={clsx(
                  "group flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left transition",
                  detail?.id === s.id
                    ? "bg-jarvis-cyan/10 text-jarvis-text"
                    : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{s.title}</p>
                  <p className="text-[10px] text-jarvis-faint">
                    {s.message_count} msg · {timeAgo(s.updated_at)}
                  </p>
                </div>
                <span className="flex items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      setStatus(s.id, "archived");
                    }}
                    className="rounded p-0.5 text-jarvis-faint hover:text-jarvis-amber"
                    title="Archive"
                  >
                    <Archive className="h-3 w-3" />
                  </span>
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      removeSession(s.id);
                    }}
                    className="rounded p-0.5 text-jarvis-faint hover:text-jarvis-rose"
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3" />
                  </span>
                </span>
              </button>
            ))
          )}
        </div>

        <button
          onClick={() => setShowArchived((v) => !v)}
          className="flex items-center justify-center gap-1.5 border-t border-jarvis-border/60 py-2.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-faint transition hover:text-jarvis-cyan"
        >
          <ArchiveRestore className="h-3 w-3" />
          {showArchived ? "Hide archived" : "Show archived"}
        </button>
        {showArchived && <ArchivedList action={action} companyId={activeCompanyId} onRestore={setStatus} />}
      </aside>

      {/* Conversation column */}
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-jarvis-border/60 px-5 py-3">
          <div className="relative flex min-w-0 items-center gap-2">
            {/* Mobile-only session picker (the sessions rail is hidden < md) */}
            <button
              onClick={() => setShowMobileSessions((v) => !v)}
              title="Sessions"
              className="press-scale flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-jarvis-border bg-jarvis-panel2/50 text-jarvis-cyan md:hidden"
            >
              <History className="h-4 w-4" />
            </button>
            {showMobileSessions && (
              <>
                <div className="fixed inset-0 z-30 md:hidden" onClick={() => setShowMobileSessions(false)} />
                <div className="absolute left-0 top-11 z-40 max-h-80 w-72 overflow-y-auto rounded-xl border border-jarvis-border bg-jarvis-panel p-2 shadow-elevated-lg md:hidden">
                  <button
                    onClick={() => {
                      newSession();
                      setShowMobileSessions(false);
                    }}
                    className="mb-1 flex w-full items-center gap-1.5 rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan"
                  >
                    <Plus className="h-3.5 w-3.5" /> New Session
                  </button>
                  {sessions.length === 0 ? (
                    <p className="px-2 py-3 text-center text-xs text-jarvis-muted">No sessions yet.</p>
                  ) : (
                    sessions.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => {
                          openSession(s.id);
                          setShowMobileSessions(false);
                        }}
                        className={clsx(
                          "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition",
                          detail?.id === s.id
                            ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                            : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">{s.title}</span>
                      </button>
                    ))
                  )}
                </div>
              </>
            )}
            {renaming ? (
              <input
                autoFocus
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={commitRename}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitRename();
                  if (e.key === "Escape") setRenaming(false);
                }}
                className="w-full max-w-sm rounded-lg border border-jarvis-cyan/50 bg-jarvis-panel2/60 px-2 py-1 text-sm text-jarvis-text focus:outline-none"
              />
            ) : (
              <button
                onClick={() => {
                  if (!detail) return;
                  setRenameValue(detail.title);
                  setRenaming(true);
                }}
                className="group flex min-w-0 items-center gap-1.5"
                title={detail ? "Rename session" : undefined}
              >
                <h1 className="truncate font-display text-sm font-semibold tracking-widest text-jarvis-text">
                  {detail ? detail.title.toUpperCase() : meta.label.toUpperCase()}
                </h1>
                {detail && <Pencil className="h-3 w-3 shrink-0 text-jarvis-faint opacity-0 transition group-hover:opacity-100" />}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Mobile-only: jump to the workspace panel (preview/deliverables/tasks) */}
            <button
              onClick={() => setMobileView("panel")}
              className="press-scale flex items-center gap-1.5 rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-jarvis-cyan xl:hidden"
            >
              <Layers className="h-3.5 w-3.5" />
              Workspace
            </button>
            <span className="hidden sm:flex">
              <SaveBadge state={saveState} savedAt={savedAt} />
            </span>
          </div>
        </div>

        {action === "web_builder" && detail && (
          <WebsiteBuildBar
            session={{
              id: detail.id,
              mode: detail.mode,
              source_url: detail.source_url,
              client_id: detail.client_id,
            }}
            companyId={activeCompanyId}
            disabled={streaming}
            onFocusStage={(k) => {
              setActiveStage(k);
              // On phones, surface the panel automatically when the build lands
              // on the finished preview so the payoff isn't hidden off-screen.
              if (k === "preview_html") setMobileView("panel");
            }}
            onCreateModeSession={async (opts) => {
              const created = await newSession(opts);
              return created?.id ?? null;
            }}
            onRefresh={async (sessionId: string) => {
              // Refresh the session actually being built (may be one the build
              // bar just created), not a stale captured detail.
              if (!sessionId) return;
              try {
                const d = await api.getWorkspace(sessionId);
                setDetail(d);
              } catch {
                /* ignore transient refresh errors */
              }
            }}
          />
        )}

        {saveState === "error" && lastAttempt && (
          <div className="flex items-center justify-between gap-2 border-b border-jarvis-rose/30 bg-jarvis-rose/10 px-5 py-2 text-xs text-jarvis-rose">
            <span>The last turn failed to complete. Your work up to the failure was saved.</span>
            <button
              onClick={retryLast}
              className="press-scale flex items-center gap-1 rounded-lg border border-jarvis-rose/40 px-2 py-1 font-semibold text-jarvis-rose transition hover:bg-jarvis-rose/20"
            >
              <RefreshCw className="h-3 w-3" /> Retry
            </button>
          </div>
        )}

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {loadingDetail ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
            </div>
          ) : !hasContent ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 shadow-glow-sm">
                <Icon className="h-6 w-6 text-jarvis-cyan" />
              </div>
              <p className="font-display text-base font-bold tracking-wide text-jarvis-text">{meta.label}</p>
              <p className="max-w-sm text-sm text-jarvis-muted">
                {meta.description}. Describe what you need below — Jarvis streams the work, fills the studio
                panels, saves every version, and tracks it as a project task.
              </p>
            </div>
          ) : (
            <>
              {detail!.messages.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={clsx("flex gap-3", m.role === "user" && "flex-row-reverse")}
                >
                  <div
                    className={clsx(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                      m.role === "user"
                        ? "border-jarvis-blue/40 bg-jarvis-blue/10 text-jarvis-blue"
                        : "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
                    )}
                  >
                    {m.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>
                  <div
                    className={clsx(
                      "max-w-[80%] rounded-2xl border px-4 py-2.5",
                      m.role === "user"
                        ? "border-jarvis-blue/30 bg-jarvis-blue/10 text-sm text-jarvis-text"
                        : "hud-panel border-jarvis-border"
                    )}
                  >
                    {m.role === "user" ? m.content : <MarkdownLite content={m.content} />}
                  </div>
                </motion.div>
              ))}

              {streaming && (
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="hud-panel max-w-[80%] rounded-2xl border border-jarvis-border px-4 py-2.5">
                    {streamText ? (
                      <MarkdownLite content={streamText} />
                    ) : (
                      <span className="flex items-center gap-1.5 text-xs text-jarvis-muted">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-jarvis-cyan [animation-delay:-0.3s]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-jarvis-cyan [animation-delay:-0.15s]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-jarvis-cyan" />
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input, activeStage);
          }}
          className="pb-safe border-t border-jarvis-border/60 p-4"
        >
          {activeStage && stages.length > 0 && (
            <div className="mb-2 flex items-center gap-1.5 text-[10px] text-jarvis-muted">
              <Layers className="h-3 w-3 text-jarvis-cyan" />
              Focused on
              <span className="rounded-full border border-jarvis-cyan/30 bg-jarvis-cyan/10 px-2 py-0.5 font-semibold text-jarvis-cyan">
                {stages.find((s) => s.state_key === activeStage)?.label ?? activeStage}
              </span>
              stage
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage(input, activeStage);
                }
              }}
              rows={1}
              placeholder={`Ask the ${meta.label}…  (Enter to send, Shift+Enter for a new line)`}
              className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
            />
            <button
              type="submit"
              disabled={streaming || !input.trim()}
              className="press-scale flex h-[44px] shrink-0 items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-4 text-sm font-medium text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
            >
              {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <CornerDownLeft className="h-4 w-4" />}
            </button>
          </div>
        </form>
      </section>

      {/* Structured workspace rail. On desktop (xl) it's a fixed right column;
          below xl it becomes a full-screen overlay toggled from the header, so
          the Website Builder preview + deliverables + tasks stay reachable on
          iPhone. */}
      <aside
        className={clsx(
          "shrink-0 flex-col border-l border-jarvis-border/60 bg-jarvis-panel/95 backdrop-blur-2xl xl:flex xl:w-96 xl:bg-jarvis-panel/40 xl:backdrop-blur-none",
          "absolute inset-0 z-20 w-full xl:static xl:z-auto",
          mobileView === "panel" ? "flex" : "hidden xl:flex"
        )}
      >
        {/* Mobile-only: back to the conversation */}
        <button
          onClick={() => setMobileView("chat")}
          className="flex items-center gap-1.5 border-b border-jarvis-border/60 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-jarvis-cyan xl:hidden"
        >
          <CornerDownLeft className="h-3.5 w-3.5 rotate-180" />
          Back to chat
        </button>
        <div className="flex border-b border-jarvis-border/60">
          {(["workspace", "deliverables", "tasks"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setRightTab(tab)}
              className={clsx(
                "flex flex-1 items-center justify-center gap-1.5 py-3 text-xs font-semibold uppercase tracking-wide transition",
                rightTab === tab
                  ? "border-b-2 border-jarvis-cyan text-jarvis-cyan"
                  : "text-jarvis-muted hover:text-jarvis-text"
              )}
            >
              {tab === "workspace" ? (
                <Layers className="h-3.5 w-3.5" />
              ) : tab === "deliverables" ? (
                <FileText className="h-3.5 w-3.5" />
              ) : (
                <ListChecks className="h-3.5 w-3.5" />
              )}
              {tab}
            </button>
          ))}
        </div>

        {rightTab === "workspace" ? (
          <div className="flex min-h-0 flex-1 flex-col">
            {/* Stage tabs */}
            {stages.length > 0 && (
              <div className="flex flex-wrap gap-1.5 border-b border-jarvis-border/60 p-2.5">
                {stages.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setActiveStage(s.state_key)}
                    className={clsx(
                      "rounded-lg px-2.5 py-1 text-[11px] font-medium transition",
                      activeStage === s.state_key
                        ? "bg-jarvis-cyan/15 text-jarvis-cyan"
                        : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
            <div className="flex-1 space-y-3 overflow-y-auto p-3">
              {!detail || !panelCtx ? (
                <p className="px-2 py-10 text-center text-xs text-jarvis-muted">
                  Start a session to build the {meta.label} workspace.
                </p>
              ) : (
                <>
                  {action === "automation" && <AutomationBanner ctx={panelCtx} />}
                  {stages
                    .filter((s) => s.state_key === activeStage || !activeStage)
                    .map((s) => (
                      <StagePanel
                        key={s.key}
                        stateKey={s.state_key}
                        label={s.label}
                        hint={s.hint}
                        ctx={panelCtx}
                      />
                    ))}
                </>
              )}
            </div>
          </div>
        ) : rightTab === "deliverables" ? (
          <div className="flex-1 space-y-3 overflow-y-auto p-3">
            {versionGroups.length === 0 ? (
              <p className="px-2 py-6 text-center text-xs text-jarvis-muted">
                Deliverables are saved here automatically — every turn is versioned.
              </p>
            ) : (
              versionGroups.map(([title, versions]) => (
                <div key={title} className="rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-3">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <FileText className="h-3 w-3 text-jarvis-cyan" />
                    <p className="truncate text-xs font-semibold text-jarvis-text">{title}</p>
                    {versions.length > 1 && (
                      <span className="ml-auto flex items-center gap-1 rounded-full bg-jarvis-panel2 px-1.5 py-0.5 text-[9px] text-jarvis-muted">
                        <Clock3 className="h-2.5 w-2.5" /> v{Math.max(...versions.map((v) => v.version ?? 1))}
                      </span>
                    )}
                  </div>
                  {versions[versions.length - 1].kind === "image" ? (
                    <img
                      src={versions[versions.length - 1].content}
                      alt={title}
                      className="w-full rounded-lg border border-jarvis-border/50 bg-white/5"
                    />
                  ) : (
                    <p className="line-clamp-4 text-[11px] leading-relaxed text-jarvis-muted">
                      {versions[versions.length - 1].content}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {detail && <AddTaskRow detail={detail} onAdded={() => openSession(detail.id)} toastErr={(m) => toast.push(m, "error")} />}
            {!detail || detail.tasks.length === 0 ? (
              <p className="px-2 py-6 text-center text-xs text-jarvis-muted">
                Tasks appear here (and in Project Manager) as work is created.
              </p>
            ) : (
              detail.tasks.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center gap-2 rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 px-3 py-2"
                >
                  <span
                    className={clsx(
                      "h-1.5 w-1.5 shrink-0 rounded-full",
                      (TASK_TONE[t.status] ?? "text-jarvis-muted").replace("text-", "bg-")
                    )}
                  />
                  <span className="min-w-0 flex-1 truncate text-xs text-jarvis-text">{t.title}</span>
                  <span
                    className={clsx(
                      "shrink-0 text-[10px] font-medium uppercase",
                      TASK_TONE[t.status] ?? "text-jarvis-muted"
                    )}
                  >
                    {t.status.replace("_", " ")}
                  </span>
                </div>
              ))
            )}
          </div>
        )}

        {detail?.project_id && (
          <div className="border-t border-jarvis-border/60 p-3">
            <a
              href="/company/projects"
              className="flex items-center justify-center gap-1.5 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 py-2 text-xs font-medium text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
            >
              Open in Project Manager →
            </a>
          </div>
        )}
      </aside>
    </main>
  );
}

// --- small pieces ---------------------------------------------------------

function SaveBadge({ state, savedAt }: { state: SaveState; savedAt: string | null }) {
  const map = {
    idle: { text: "Auto-save on", cls: "text-jarvis-muted", icon: <Check className="h-3 w-3" /> },
    streaming: { text: "Streaming…", cls: "text-jarvis-cyan", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    saved: {
      text: savedAt ? `Saved · ${timeAgo(savedAt)}` : "All changes saved",
      cls: "text-jarvis-emerald",
      icon: <Check className="h-3 w-3" />,
    },
    error: { text: "Save failed", cls: "text-jarvis-rose", icon: <X className="h-3 w-3" /> },
  }[state];
  return (
    <span
      className={clsx(
        "flex shrink-0 items-center gap-1.5 rounded-full border border-jarvis-border/70 bg-jarvis-panel2/40 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        map.cls
      )}
    >
      {map.icon}
      {map.text}
    </span>
  );
}

function AddTaskRow({
  detail,
  onAdded,
  toastErr,
}: {
  detail: WorkspaceDetail;
  onAdded: () => void;
  toastErr: (m: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  async function add() {
    const t = title.trim();
    if (!t || busy) return;
    setBusy(true);
    try {
      await api.addWorkspaceTask(detail.id, { title: t });
      setTitle("");
      onAdded();
    } catch (err) {
      toastErr(err instanceof ApiError ? err.message : "Couldn't add the task.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex items-center gap-1.5">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && add()}
        placeholder="Add a task to this project…"
        className="flex-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-2.5 py-1.5 text-xs text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
      />
      <button
        onClick={add}
        disabled={busy || !title.trim()}
        className="press-scale flex h-[30px] w-[30px] items-center justify-center rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function ArchivedList({
  action,
  companyId,
  onRestore,
}: {
  action: string;
  companyId: string | null;
  onRestore: (id: string, status: "active" | "archived") => void;
}) {
  const [items, setItems] = useState<WorkspaceSummary[]>([]);
  useEffect(() => {
    api
      .listWorkspaces({ companyId: companyId ?? "none", action, status: "archived" })
      .then(setItems)
      .catch(() => setItems([]));
  }, [action, companyId]);
  if (items.length === 0)
    return <p className="px-3 py-2 text-center text-[10px] text-jarvis-faint">No archived sessions.</p>;
  return (
    <div className="max-h-40 space-y-1 overflow-y-auto px-2 pb-2">
      {items.map((s) => (
        <div
          key={s.id}
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-jarvis-muted"
        >
          <span className="min-w-0 flex-1 truncate">{s.title}</span>
          <button
            onClick={() => {
              onRestore(s.id, "active");
              setItems((prev) => prev.filter((x) => x.id !== s.id));
            }}
            className="shrink-0 rounded p-0.5 text-jarvis-faint hover:text-jarvis-emerald"
            title="Restore"
          >
            <ArchiveRestore className="h-3 w-3" />
          </button>
        </div>
      ))}
    </div>
  );
}
