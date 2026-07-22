import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, ExternalLink, SquarePen, Wrench, X } from "lucide-react";

import { api, ApiError } from "@/api/client";
import JarvisCore from "@/components/JarvisCore";
import { useCompany } from "@/context/CompanyContext";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useWorkspace } from "@/hooks/useWorkspace";
import { useCoreState } from "@/hooks/useCoreState";
import type { ChatMessage, ToolCallLog } from "@/types";

const PERSONA_KEY = "jarvis_active_persona";

/**
 * The AI Core as the central brain — a global "command Jarvis" surface reachable
 * from every screen (not just Home). It drives the SAME real chat/capability
 * pipeline the Chat page uses (api.chat → memory + tools + approval-gated
 * actions), scoped to the active workspace, and the Core visibly reflects live
 * state (idle / thinking / waiting-for-approval). This is functional, not
 * decorative: you can ask a question or issue a command from anywhere and Jarvis
 * actually answers and can act (surfacing the tools it ran).
 */
export default function CoreCommandSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { activeCompany, activeCompanyId } = useCompany();
  const workspace = useWorkspace();
  const { setStatus } = useAssistantStatus();
  const coreState = useCoreState();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Persist the conversation PER WORKSPACE so it survives closing the sheet,
  // navigating, and full reloads — and each workspace keeps its own thread.
  const threadKey = `jarvis_core_thread_${activeCompanyId ?? "global"}`;
  useEffect(() => {
    try {
      const saved = localStorage.getItem(threadKey);
      setMessages(saved ? (JSON.parse(saved) as ChatMessage[]) : []);
    } catch {
      setMessages([]);
    }
  }, [threadKey]);
  useEffect(() => {
    try {
      if (messages.length) localStorage.setItem(threadKey, JSON.stringify(messages.slice(-60)));
    } catch {
      /* storage full / unavailable — thread still lives in memory this session */
    }
  }, [messages, threadKey]);

  function newThread() {
    setMessages([]);
    try {
      localStorage.removeItem(threadKey);
    } catch {
      /* ignore */
    }
    inputRef.current?.focus();
  }

  function goto(path: string) {
    navigate(path);
    onClose();
  }

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 120);
  }, [open]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const persona = (() => {
      try {
        return localStorage.getItem(PERSONA_KEY) || "ceo_assistant";
      } catch {
        return "ceo_assistant";
      }
    })();
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setStatus("thinking");
    try {
      const res = await api.chat(next, activeCompanyId, persona);
      setMessages([...next, { role: "assistant", content: res.text, toolCalls: res.tool_calls }]);
    } catch (err) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: err instanceof ApiError ? err.message : "Couldn't reach Jarvis. Check the AI provider key in .env.",
        },
      ]);
    } finally {
      setBusy(false);
      setStatus("idle");
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm"
          />
          {/* Bottom sheet on mobile; centered panel on desktop. */}
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.98 }}
            transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-x-0 bottom-0 z-[61] mx-auto flex max-h-[85vh] w-full max-w-2xl flex-col rounded-t-3xl border border-jarvis-border/70 bg-jarvis-panel/95 backdrop-blur-2xl pb-safe shadow-elevated-lg sm:inset-x-4 sm:bottom-6 sm:rounded-3xl"
            style={{ borderColor: "var(--ws-accent-soft)" }}
          >
            {/* Header: the Core (live state) + workspace identity */}
            <div className="flex items-center gap-3 border-b border-jarvis-border/50 px-4 py-3">
              <JarvisCore state={coreState} size={40} />
              <div className="min-w-0 flex-1">
                <p className="font-display text-sm font-semibold tracking-wide text-jarvis-text">
                  Ask Jarvis
                </p>
                <p className="truncate text-[11px] text-jarvis-muted">
                  {activeCompany ? `${activeCompany.name} · ${workspace.role}` : "AI Operating System"}
                </p>
              </div>
              {messages.length > 0 && (
                <button
                  onClick={newThread}
                  title="New conversation"
                  aria-label="New conversation"
                  className="press-scale rounded-lg p-2 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                >
                  <SquarePen className="h-4 w-4" />
                </button>
              )}
              <button
                onClick={onClose}
                aria-label="Close"
                className="press-scale rounded-lg p-2 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Conversation */}
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
              {messages.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <p className="text-sm text-jarvis-muted">
                    Ask anything about {activeCompany?.name ?? "your workspace"} — products, tasks, emails, or
                    tell Jarvis to do something. It uses this workspace's memory and can act (with your approval).
                  </p>
                </div>
              )}
              <div className="space-y-3">
                {messages.map((m, i) => (
                  <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div
                      className={
                        m.role === "user"
                          ? "max-w-[85%] rounded-2xl rounded-br-sm bg-jarvis-panel2/70 px-3.5 py-2 text-sm text-jarvis-text"
                          : "max-w-[85%] rounded-2xl rounded-bl-sm border border-jarvis-border/50 bg-jarvis-panel/60 px-3.5 py-2 text-sm text-jarvis-text"
                      }
                    >
                      <p className="whitespace-pre-wrap">{m.content}</p>
                      {m.toolCalls && m.toolCalls.length > 0 && (
                        <ToolCalls calls={m.toolCalls} onNavigate={goto} />
                      )}
                    </div>
                  </div>
                ))}
                {busy && (
                  <div className="flex items-center gap-2 text-xs text-jarvis-muted">
                    <JarvisCore state="thinking" size={20} /> Thinking…
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>

            {/* Command input */}
            <div className="border-t border-jarvis-border/50 p-3">
              <div className="flex items-end gap-2 rounded-2xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 focus-within:border-[color:var(--ws-accent-soft)]">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  rows={1}
                  placeholder="Command or ask Jarvis…"
                  className="max-h-28 min-h-[24px] flex-1 resize-none bg-transparent text-sm text-jarvis-text placeholder:text-jarvis-faint focus:outline-none"
                />
                <button
                  onClick={send}
                  disabled={!input.trim() || busy}
                  aria-label="Send"
                  className="press-scale flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-jarvis-bg transition disabled:opacity-40"
                  style={{ backgroundColor: "var(--ws-accent)" }}
                >
                  <CornerDownLeft className="h-4 w-4" />
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Where a tool's result can be viewed in the UI — turns an AI action into a
// tap-through to the relevant manager (connects the Core to Project/Task work).
const TOOL_DESTINATION: Record<string, { label: string; path: string }> = {
  create_task: { label: "Open Task Manager", path: "/company/projects" },
  create_project: { label: "Open Project Manager", path: "/company/projects" },
  propose_update_product: { label: "Open Brand Brain", path: "/company/brand-brain" },
  propose_send_email: { label: "Review approvals", path: "/approvals" },
  propose_create_calendar_event: { label: "Review approvals", path: "/approvals" },
};

function ToolCalls({ calls, onNavigate }: { calls: ToolCallLog[]; onNavigate: (path: string) => void }) {
  return (
    <div className="mt-2 space-y-1.5 border-t border-jarvis-border/40 pt-2">
      {calls.map((c, i) => {
        const dest = !c.is_error ? TOOL_DESTINATION[c.name] : undefined;
        return (
          <div key={i} className="flex items-center gap-2 text-[11px] text-jarvis-muted">
            <Wrench className={c.is_error ? "h-3 w-3 shrink-0 text-jarvis-rose" : "h-3 w-3 shrink-0 text-jarvis-cyan"} />
            <span className="font-medium text-jarvis-text">{c.name}</span>
            <span>{c.is_error ? "failed" : "ran"}</span>
            {dest && (
              <button
                onClick={() => onNavigate(dest.path)}
                className="ml-auto flex items-center gap-1 rounded-md px-1.5 py-0.5 font-medium transition-colors hover:bg-jarvis-panel2/60"
                style={{ color: "var(--ws-accent)" }}
              >
                {dest.label} <ExternalLink className="h-3 w-3" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
