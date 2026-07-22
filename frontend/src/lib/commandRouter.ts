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

export function threadKey(companyId: string | null): string {
  return `jarvis_core_thread_${companyId ?? "global"}`;
}

export function loadThread(companyId: string | null): CommandMessage[] {
  try {
    const saved = localStorage.getItem(threadKey(companyId));
    return saved ? (JSON.parse(saved) as CommandMessage[]) : [];
  } catch {
    return [];
  }
}

export function saveThread(companyId: string | null, messages: CommandMessage[]): void {
  try {
    localStorage.setItem(threadKey(companyId), JSON.stringify(messages.slice(-60)));
  } catch {
    /* storage full / unavailable — the thread still lives in memory */
  }
}

export function clearThread(companyId: string | null): void {
  try {
    localStorage.removeItem(threadKey(companyId));
  } catch {
    /* ignore */
  }
}

/** Append a completed turn to the shared thread (used by non-React surfaces). */
export function appendTurn(
  companyId: string | null,
  request: string,
  outcome: CommandOutcome
): CommandMessage[] {
  const next: CommandMessage[] = [
    ...loadThread(companyId),
    { role: "user", content: request },
    {
      role: "assistant",
      content: outcome.reply,
      toolCalls: outcome.toolCalls,
      decision: outcome.decision,
    },
  ];
  saveThread(companyId, next);
  return next;
}
