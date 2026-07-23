import { api, ApiError } from "@/api/client";
import type { JarvisCoreState } from "@/components/JarvisCore";
import type { ChatMessage, CommandDecision, ToolCallLog } from "@/types";

/**
 * THE single intelligence pipeline.
 *
 * Every way of commanding Jarvis — typing in Ask Jarvis, speaking to the Orb,
 * the home console, a phone, a watch, or any future interface — calls
 * `routeAndExecute` and nothing else. Nothing bypasses the router: a request is
 * classified (POST /command-center/route), then executed by the subsystem that
 * owns it, with the same memory, the same tools, and the same approval gate on
 * real-world actions.
 *
 * Surfaces differ only in PRESENTATION: this returns what to show, what to say
 * aloud, and where (if anywhere) to hand off — the caller decides how to render
 * that. Adding a new interface means calling this function; it never means
 * adding a second pipeline.
 */

const PERSONA_KEY = "jarvis_active_persona";

export function activePersona(): string {
  try {
    return localStorage.getItem(PERSONA_KEY) || "ceo_assistant";
  } catch {
    return "ceo_assistant";
  }
}

/** A turn in the thread, tagged with the decision that produced it. */
export type CommandMessage = ChatMessage & { decision?: CommandDecision };

// The Core's state mirrors the kind of work the destination implies, so the orb
// communicates what Jarvis is actually doing — not just "thinking". Shared, so
// every surface's orb reacts identically.
const CORE_STATE: Record<string, JarvisCoreState> = {
  deep_research: "researching",
  web_builder: "generating",
  logo_design: "generating",
  product_creation: "generating",
  code_writer: "generating",
  automation: "generating",
  work_queue: "generating",
};

export function coreStateFor(destination: string | undefined): JarvisCoreState {
  return (destination && CORE_STATE[destination]) || "thinking";
}

export interface CommandOutcome {
  decision: CommandDecision;
  /** Full text to display in a thread. */
  reply: string;
  /** Short form to read aloud (long plans don't make good speech). */
  speech: string;
  toolCalls?: ToolCallLog[];
  /** Where this request was handed off to, if anywhere — the caller navigates. */
  handoffPath: string | null;
}

export interface RouteOptions {
  companyId: string | null;
  /** Prior turns, so routing and answers keep conversation context. */
  history?: CommandMessage[];
  /** Live status as work progresses ("Thinking…" → "Researching…" → …). */
  onStatus?: (status: string, decision?: CommandDecision) => void;
}

// Used when routing itself is unreachable — still answer, via chat.
function chatFallback(): CommandDecision {
  return {
    destination: "chat",
    label: "Chat",
    mode: "chat",
    target: null,
    status: "Thinking…",
    explanation: "",
    clarifying_question: null,
  };
}

export async function routeAndExecute(request: string, opts: RouteOptions): Promise<CommandOutcome> {
  const { companyId, history = [], onStatus } = opts;
  const wire = [...history, { role: "user" as const, content: request }].map((m) => ({
    role: m.role,
    content: m.content,
  }));

  onStatus?.("Thinking…");
  let decision: CommandDecision;
  try {
    decision = await api.routeCommand(request, companyId, wire.slice(-6));
  } catch {
    decision = chatFallback();
  }
  onStatus?.(decision.status, decision);

  // Only asked when routing genuinely can't proceed — otherwise Jarvis assumes.
  if (decision.clarifying_question) {
    return {
      decision,
      reply: decision.clarifying_question,
      speech: decision.clarifying_question,
      handoffPath: null,
    };
  }

  try {
    if (decision.mode === "chat") {
      const res = await api.chat(wire, companyId, activePersona());
      return { decision, reply: res.text, speech: res.text, toolCalls: res.tool_calls, handoffPath: null };
    }

    if (decision.mode === "work_queue") {
      onStatus?.("Planning…", decision);
      const run = await api.createWorkPlan(request, companyId);
      const steps = run.subtasks.map((s, i) => `${i + 1}. ${s.title}`).join("\n");
      const n = run.subtasks.length;
      return {
        decision,
        reply: `${decision.explanation}\n\nHere's the plan — I'll work through it and stop for your approval on anything with real-world consequences:\n${steps}`,
        speech: `${decision.explanation} I've broken it into ${n} step${n === 1 ? "" : "s"} and I'm starting now. I'll stop for your approval on anything with real-world consequences.`,
        // Runs the steps in sequence, live, on arrival.
        handoffPath: `/company/work-queue?run=${run.id}&autorun=1`,
      };
    }

    // studio / navigate — the studio picks the request up from `ask` and starts
    // working immediately, so nothing has to be retyped.
    const path =
      decision.mode === "studio"
        ? `/studio/${decision.target}?ask=${encodeURIComponent(request)}`
        : decision.target ?? "/";
    const line = `${decision.explanation} Opening ${decision.label}…`;
    return { decision, reply: line, speech: line, handoffPath: path };
  } catch (err) {
    const message =
      err instanceof ApiError ? err.message : "Couldn't reach Jarvis. Check the AI provider key in .env.";
    return { decision, reply: message, speech: message, handoffPath: null };
  }
}

/* ------------------------------------------------------------------ *
 * Shared conversation thread — one per workspace, shared by every
 * interface, so speaking and typing continue the SAME conversation.
 * ------------------------------------------------------------------ */

/**
 * The thread lives in the BACKEND, not in this browser.
 *
 * It used to be a localStorage key per workspace, which meant a Mac and an
 * iPhone held genuinely different histories for the same conversation. It is
 * now a `chat` WorkspaceSession: stored once, scoped by owner and company, and
 * broadcast as the "conversations" kind by the existing sync architecture — no
 * second sync path, no polling.
 *
 * localStorage keeps exactly two things, neither of them a source of truth:
 *   * a migration-complete marker, so the one-time upload runs once;
 *   * which thread THIS device has open, because conversation selection is
 *     deliberately per-device — opening a different conversation on the phone
 *     must not yank the Mac's screen to a different conversation.
 */

/** Legacy key. Read once during migration, then never written again. */
export function threadKey(companyId: string | null): string {
  return `jarvis_core_thread_${companyId ?? "global"}`;
}

const migratedKey = (companyId: string | null) => `jarvis_thread_migrated_${companyId ?? "global"}`;
/** Per-device selection — which thread this screen has open. Not shared. */
const selectedKey = (companyId: string | null) => `jarvis_thread_selected_${companyId ?? "global"}`;

/** In-memory render cache. Disposable: every load refetches from the backend. */
const cache = new Map<string, CommandMessage[]>();

export function cachedThread(companyId: string | null): CommandMessage[] {
  return cache.get(companyId ?? "global") ?? [];
}

function toMessages(raw: unknown): CommandMessage[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((m): m is Record<string, unknown> => !!m && typeof m === "object")
    .map((m) => ({
      role: (m.role === "assistant" ? "assistant" : "user") as CommandMessage["role"],
      content: String(m.content ?? ""),
      toolCalls: m.toolCalls as CommandMessage["toolCalls"],
      decision: m.decision as CommandMessage["decision"],
    }));
}

/** The backend thread for this workspace, creating it on first use. */
export async function ensureThreadId(companyId: string | null): Promise<string | null> {
  const remembered = localStorage.getItem(selectedKey(companyId));
  if (remembered) return remembered;
  try {
    const existing = await api.listWorkspaces({ companyId: companyId ?? "none", action: "chat" });
    const found = existing.find((s) => s.action === "chat");
    const id = found ? found.id : (await api.createWorkspace({ action: "chat", company_id: companyId })).id;
    localStorage.setItem(selectedKey(companyId), id);
    return id;
  } catch {
    return null;
  }
}

/**
 * The one-time migration of whatever this device still holds locally.
 *
 * Deliberately conservative: it uploads, then re-reads and confirms the backend
 * actually has the messages before marking itself done. Local history is left
 * untouched either way — a failed migration must never be the reason a
 * conversation disappears. Duplicates are the backend's job (turns are
 * deduplicated by role+content+timestamp), so both devices can safely upload
 * overlapping history.
 */
async function migrateLocalHistory(companyId: string | null, threadId: string): Promise<void> {
  if (localStorage.getItem(migratedKey(companyId))) return;
  let local: CommandMessage[] = [];
  try {
    const raw = localStorage.getItem(threadKey(companyId));
    local = raw ? (JSON.parse(raw) as CommandMessage[]) : [];
  } catch {
    local = [];
  }
  if (local.length === 0) {
    localStorage.setItem(migratedKey(companyId), "empty");
    return;
  }
  try {
    await api.appendWorkspaceTurns(
      threadId,
      local.map((m) => ({ role: m.role, content: m.content })),
    );
    // Verify persistence before declaring victory.
    const stored = toMessages((await api.getWorkspace(threadId)).messages);
    const persisted = local.every((m) => stored.some((s) => s.content === m.content && s.role === m.role));
    if (persisted) localStorage.setItem(migratedKey(companyId), new Date().toISOString());
    // If not persisted: no marker is written, local history stays put, and the
    // next load tries again. Nothing is lost and nothing is claimed.
  } catch {
    /* Same: leave the local copy alone and retry next time. */
  }
}

export async function loadThread(companyId: string | null): Promise<CommandMessage[]> {
  const id = await ensureThreadId(companyId);
  if (!id) return cachedThread(companyId);
  await migrateLocalHistory(companyId, id);
  try {
    const messages = toMessages((await api.getWorkspace(id)).messages);
    cache.set(companyId ?? "global", messages);
    return messages;
  } catch {
    return cachedThread(companyId);
  }
}

/** Start a fresh conversation on THIS device. Shared history is not deleted. */
export async function clearThread(companyId: string | null): Promise<void> {
  cache.delete(companyId ?? "global");
  try {
    const created = await api.createWorkspace({ action: "chat", company_id: companyId });
    localStorage.setItem(selectedKey(companyId), created.id);
  } catch {
    localStorage.removeItem(selectedKey(companyId));
  }
}

/** Append a completed turn. Saving is what broadcasts it to every device. */
export async function appendTurn(
  companyId: string | null,
  request: string,
  outcome: CommandOutcome
): Promise<CommandMessage[]> {
  const id = await ensureThreadId(companyId);
  const turns = [
    { role: "user", content: request },
    { role: "assistant", content: outcome.reply },
  ];
  if (!id) return cachedThread(companyId);
  try {
    const saved = await api.appendWorkspaceTurns(id, turns);
    const messages = toMessages(saved.messages);
    cache.set(companyId ?? "global", messages);
    return messages;
  } catch {
    return cachedThread(companyId);
  }
}
