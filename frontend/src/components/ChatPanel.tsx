import { useEffect, useRef, useState, type FormEvent, type SyntheticEvent } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  CornerDownLeft,
  Hand,
  Mic,
  MousePointerClick,
  Repeat,
  User,
  Volume2,
  VolumeX,
  Wrench,
} from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import JarvisCore, { type JarvisCoreState } from "@/components/JarvisCore";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";
import { useMicrophoneDevices } from "@/hooks/useMicrophoneDevices";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import type { ChatMessage, Persona, ToolCallLog } from "@/types";

const VOICE_STATE_LABEL: Record<JarvisCoreState, string> = {
  idle: "Online",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

const VOICE_STATE_DOT: Record<JarvisCoreState, string> = {
  idle: "bg-jarvis-emerald",
  listening: "bg-jarvis-rose",
  thinking: "bg-jarvis-violet",
  speaking: "bg-jarvis-cyan",
};

const PERSONA_STORAGE_KEY = "jarvis_active_persona";

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Systems online. I can build websites, design logos, spec products, run deep research, write code, manage projects, and automate workflows. What are we working on?",
};

function humanizeToolName(name: string): string {
  return name
    .replace(/^run_/, "")
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

function ToolCallCard({ call }: { call: ToolCallLog }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={clsx(
        "rounded-xl border text-xs",
        call.is_error
          ? "border-jarvis-rose/40 bg-jarvis-rose/5"
          : "border-jarvis-cyan/30 bg-jarvis-cyan/5"
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {call.is_error ? (
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-jarvis-rose" />
        ) : (
          <Wrench className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan" />
        )}
        <span
          className={clsx(
            "flex-1 font-medium",
            call.is_error ? "text-jarvis-rose" : "text-jarvis-cyan"
          )}
        >
          {call.is_error ? "Failed: " : "Ran: "}
          {humanizeToolName(call.name)}
        </span>
        {!call.is_error && <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-jarvis-emerald" />}
        <ChevronDown className={clsx("h-3.5 w-3.5 shrink-0 text-jarvis-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-2 border-t border-jarvis-border/40 px-3 py-2">
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-jarvis-muted">Input</p>
            <pre className="whitespace-pre-wrap break-words font-data text-[11px] text-jarvis-text">
              {JSON.stringify(call.input, null, 2)}
            </pre>
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-jarvis-muted">Result</p>
            <p className="whitespace-pre-wrap break-words text-jarvis-text">{call.output}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function voiceErrorMessage(kind: string | null): string | null {
  switch (kind) {
    case "not-allowed":
      return "Microphone access was denied. Allow microphone access for this site in your browser's settings, then try again.";
    case "audio-capture":
      return "No microphone was found. Check that one is connected and try again.";
    case "no-speech":
      return "Didn't catch that — try again.";
    case "unsupported":
      return "Voice input isn't supported in this browser. Try Chrome, Edge, or Safari.";
    case "other":
      return "Voice input hit an unexpected error. Try again.";
    default:
      return null;
  }
}

interface ChatPanelProps {
  // Set by CEO Dashboard quick actions ("Read my email", "Show today's
  // calendar", ...) via a /chat?prompt=... query param — sent once,
  // automatically, on mount rather than requiring the user to retype it.
  autoPrompt?: string;
  // Set by the "Start voice mode" quick action (/chat?voice=1) — opens
  // straight into listening instead of requiring an extra mic click.
  autoVoice?: boolean;
}

export default function ChatPanel({ autoPrompt, autoVoice }: ChatPanelProps = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoTriggered = useRef(false);

  // Continuous conversation: once on, Jarvis automatically starts listening
  // again as soon as its own spoken reply finishes, so a back-and-forth
  // voice conversation never needs another mic click. Push-to-talk: swaps
  // the mic button from tap-to-toggle to hold-to-talk (release to send).
  const [continuousMode, setContinuousMode] = useState(false);
  const [pushToTalk, setPushToTalk] = useState(false);
  const continuousModeRef = useRef(continuousMode);
  continuousModeRef.current = continuousMode;

  const {
    supported: speechOutputSupported,
    muted,
    toggleMuted,
    speak,
    cancel: cancelSpeech,
    speaking,
  } = useSpeechSynthesis();
  const {
    supported: micDevicesSupported,
    devices: micDevices,
    selectedId: selectedMicId,
    permissionGranted: micPermissionGranted,
    requestAccess: requestMicAccess,
    selectDevice: selectMicDevice,
  } = useMicrophoneDevices();
  const { activeCompanyId } = useCompany();
  const { setStatus: setGlobalAssistantStatus } = useAssistantStatus();

  // "AI Executives" persona switcher — all personas share the same
  // memory/tools, this just changes framing/tone via the backend's system
  // prompt. Persisted so it survives reloads, same pattern as mute.
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<string>(
    () => localStorage.getItem(PERSONA_STORAGE_KEY) || "ceo_assistant"
  );
  useEffect(() => {
    api.listPersonas().then(setPersonas).catch(() => setPersonas([]));
  }, []);
  useEffect(() => {
    localStorage.setItem(PERSONA_STORAGE_KEY, persona);
  }, [persona]);

  async function sendMessage(content: string) {
    const trimmed = content.trim();
    if (!trimmed || sending) return;

    const nextMessages = [...messages, { role: "user", content: trimmed } as ChatMessage];
    setMessages(nextMessages);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await api.chat(
        nextMessages.map(({ role, content }) => ({ role, content })),
        activeCompanyId,
        persona
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.text, toolCalls: res.tool_calls },
      ]);
      // In continuous mode, resume listening the instant Jarvis finishes
      // speaking — that's the whole "talk naturally, back and forth"
      // experience. Outside continuous mode this is a no-op beyond TTS.
      speak(res.text, () => {
        if (continuousModeRef.current && micSupportedRef.current) {
          startListeningRef.current();
        }
      });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't reach the AI provider. Check your API keys in .env."
      );
    } finally {
      setSending(false);
      requestAnimationFrame(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  }

  const {
    supported: micSupported,
    listening,
    error: voiceError,
    interimTranscript,
    start: startListening,
    stop: stopListening,
  } = useSpeechRecognition({
    onFinalResult: (transcript) => {
      setInput(transcript);
      sendMessage(transcript);
    },
  });

  // Refs so the speak() onEnd closure above (created once per sendMessage
  // call) always sees the latest start()/support value without having to
  // re-run the whole hook order. Also backs the global keyboard-shortcut
  // listener below, which registers once and needs live values too.
  const micSupportedRef = useRef(micSupported);
  micSupportedRef.current = micSupported;
  const startListeningRef = useRef(startListening);
  startListeningRef.current = startListening;
  const stopListeningRef = useRef(stopListening);
  stopListeningRef.current = stopListening;
  const listeningRef = useRef(listening);
  listeningRef.current = listening;
  const cancelSpeechRef = useRef(cancelSpeech);
  cancelSpeechRef.current = cancelSpeech;

  // Mirror the live transcript into the input box while the user is speaking.
  useEffect(() => {
    if (listening && interimTranscript) {
      setInput(interimTranscript);
    }
  }, [listening, interimTranscript]);

  // JarvisCore's single source of truth for which state to render — priority
  // order matters: actively listening/speaking is more "current" than the
  // network round-trip in between.
  const coreState: JarvisCoreState = listening ? "listening" : speaking ? "speaking" : sending ? "thinking" : "idle";

  // Broadcast to the Sidebar's persistent orb so "Jarvis is thinking" is
  // visible even if you're not looking at this panel. Resets to idle on
  // unmount (e.g. navigating away mid-request) rather than leaving the
  // global indicator stuck on a stale state this panel can no longer update.
  useEffect(() => {
    setGlobalAssistantStatus(coreState);
  }, [coreState, setGlobalAssistantStatus]);
  useEffect(() => {
    return () => setGlobalAssistantStatus("idle");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fire at most once per mount — a Quick Action navigated here with
  // ?prompt=... or ?voice=1 already set, so act on it immediately rather
  // than waiting for the user to type/click again.
  useEffect(() => {
    if (autoTriggered.current) return;
    autoTriggered.current = true;
    if (autoPrompt) {
      sendMessage(autoPrompt);
    } else if (autoVoice && micSupported) {
      startListening();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  // Interrupt/barge-in: starting to talk always cuts Jarvis off mid-reply
  // rather than waiting for TTS to finish, in both tap and push-to-talk mode.
  function beginListening() {
    if (!micSupported || listening) return;
    cancelSpeech();
    startListening();
  }

  function handleMicClick() {
    if (!micSupported || pushToTalk) return;
    if (listening) stopListening();
    else beginListening();
  }

  function handleMicPressStart(e: SyntheticEvent) {
    if (!pushToTalk) return;
    e.preventDefault();
    beginListening();
  }

  function handleMicPressEnd(e: SyntheticEvent) {
    if (!pushToTalk) return;
    e.preventDefault();
    if (listening) stopListening();
  }

  // Keyboard shortcut: hold Space to talk, release to stop — a global
  // push-to-talk that works no matter whether the Tap/Hold mouse mode is
  // set, and interrupts Jarvis mid-reply the same way the mic button does
  // (beginListening's barge-in logic, reimplemented here via refs since
  // this listener is registered once rather than re-bound every render).
  // Ignored while the user is actually typing into a text field so Space
  // still just types a space.
  useEffect(() => {
    function isTypingTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.code !== "Space" || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;
      if (!micSupportedRef.current || listeningRef.current) return;
      e.preventDefault();
      cancelSpeechRef.current();
      startListeningRef.current();
    }

    function onKeyUp(e: KeyboardEvent) {
      if (e.code !== "Space") return;
      if (isTypingTarget(e.target)) return;
      if (!listeningRef.current) return;
      e.preventDefault();
      stopListeningRef.current();
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  const voiceMessage = voiceErrorMessage(voiceError);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-3">
          <JarvisCore state={coreState} size={28} />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            JARVIS ASSISTANT
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {personas.length > 0 && (
            <select
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              title="Which AI Executive is answering — all share the same memory and tools"
              className="rounded-lg border border-jarvis-border bg-jarvis-panel2/60 px-2 py-1.5 text-[11px] font-medium text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
            >
              {personas.map((p) => (
                <option key={p.key} value={p.key} className="bg-jarvis-panel text-jarvis-text">
                  {p.label}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => setPushToTalk((v) => !v)}
            disabled={!micSupported}
            title={pushToTalk ? "Push-to-talk: hold the mic button to speak" : "Tap-to-talk: click the mic to start/stop"}
            className={clsx(
              "flex items-center gap-1 rounded-lg border px-2 py-1.5 text-[10px] font-medium uppercase tracking-wide transition",
              !micSupported
                ? "cursor-not-allowed border-jarvis-border/50 text-jarvis-muted/50"
                : pushToTalk
                  ? "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
                  : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted hover:text-jarvis-text"
            )}
          >
            {pushToTalk ? <Hand className="h-3 w-3" /> : <MousePointerClick className="h-3 w-3" />}
            {pushToTalk ? "Hold" : "Tap"}
          </button>
          <button
            type="button"
            onClick={() => setContinuousMode((v) => !v)}
            disabled={!micSupported || !speechOutputSupported}
            title={
              continuousMode
                ? "Continuous conversation is on — Jarvis auto-listens after replying"
                : "Turn on continuous conversation (auto-listen after Jarvis replies)"
            }
            className={clsx(
              "flex items-center gap-1 rounded-lg border px-2 py-1.5 text-[10px] font-medium uppercase tracking-wide transition",
              !micSupported || !speechOutputSupported
                ? "cursor-not-allowed border-jarvis-border/50 text-jarvis-muted/50"
                : continuousMode
                  ? "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald"
                  : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted hover:text-jarvis-text"
            )}
          >
            <Repeat className="h-3 w-3" />
            Continuous
          </button>
          <button
            type="button"
            onClick={toggleMuted}
            disabled={!speechOutputSupported}
            title={
              !speechOutputSupported
                ? "Spoken replies aren't supported in this browser"
                : muted
                  ? "Unmute Jarvis's voice"
                  : "Mute Jarvis's voice"
            }
            className={clsx(
              "rounded-lg border p-1.5 transition",
              !speechOutputSupported
                ? "cursor-not-allowed border-jarvis-border/50 text-jarvis-muted/50"
                : muted
                  ? "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted hover:text-jarvis-text"
                  : "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
            )}
          >
            {muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
          </button>
          {micDevicesSupported && (
            <select
              value={selectedMicId}
              onFocus={() => {
                // Device labels are blank until permission is granted once —
                // priming here means the dropdown is populated with real
                // names by the time the user actually opens it.
                if (!micPermissionGranted) requestMicAccess();
              }}
              onChange={(e) => {
                const id = e.target.value;
                if (id) requestMicAccess(id);
                else selectMicDevice("");
              }}
              title="Preferred microphone (e.g. a USB mic) — note: the browser's speech recognition always follows your OS/browser default input regardless of this setting, so also set it as default there if it isn't picked up automatically"
              className="max-w-[9rem] rounded-lg border border-jarvis-border bg-jarvis-panel2/60 px-2 py-1.5 text-[11px] font-medium text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
            >
              <option value="" className="bg-jarvis-panel text-jarvis-text">
                System default mic
              </option>
              {micDevices.map((d, i) => (
                <option key={d.deviceId || i} value={d.deviceId} className="bg-jarvis-panel text-jarvis-text">
                  {d.label || `Microphone ${i + 1}`}
                </option>
              ))}
            </select>
          )}
          <span
            className="flex items-center gap-1.5 text-xs text-jarvis-muted"
            title="Hold Space (or the mic button) to talk"
          >
            <span className={clsx("h-1.5 w-1.5 animate-pulseGlow rounded-full", VOICE_STATE_DOT[coreState])} />
            {VOICE_STATE_LABEL[coreState]}
          </span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {messages.length === 1 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col items-center justify-center gap-3 py-6"
          >
            <JarvisCore state={coreState} size={140} />
            <p className="text-xs uppercase tracking-[0.3em] text-jarvis-faint">Systems Online</p>
          </motion.div>
        )}
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${
                m.role === "user"
                  ? "border-jarvis-blue/40 bg-jarvis-blue/10 text-jarvis-blue"
                  : "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
              }`}
            >
              {m.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            <div className={clsx("flex max-w-[75%] flex-col gap-2", m.role === "user" && "items-end")}>
              {!!m.toolCalls?.length && (
                <div className="flex w-full flex-col gap-1.5">
                  {m.toolCalls.map((call, ci) => (
                    <ToolCallCard key={ci} call={call} />
                  ))}
                </div>
              )}
              <div
                className={`rounded-2xl border px-4 py-2.5 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "border-jarvis-blue/30 bg-jarvis-blue/10 text-jarvis-text"
                    : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-text"
                }`}
              >
                {m.content}
              </div>
            </div>
          </motion.div>
        ))}
        {sending && (
          <div className="flex items-center gap-2 pl-11 text-xs text-jarvis-muted">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-jarvis-cyan [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-jarvis-cyan [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-jarvis-cyan" />
          </div>
        )}
        {error && <p className="pl-11 text-xs text-jarvis-rose">{error}</p>}
      </div>

      {listening && (
        <div className="flex items-center gap-2 border-t border-jarvis-border/60 bg-jarvis-rose/5 px-5 py-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-jarvis-rose opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-jarvis-rose" />
          </span>
          <span className="text-xs font-medium uppercase tracking-widest text-jarvis-rose">
            {pushToTalk ? "Listening — release to send..." : "Listening..."}
          </span>
          {interimTranscript && (
            <span className="truncate text-xs text-jarvis-muted">{interimTranscript}</span>
          )}
        </div>
      )}
      {voiceMessage && (
        <p className="border-t border-jarvis-border/60 px-5 py-2 text-xs text-jarvis-rose">
          {voiceMessage}
        </p>
      )}

      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-jarvis-border/60 p-4">
        <button
          type="button"
          onClick={handleMicClick}
          onMouseDown={handleMicPressStart}
          onMouseUp={handleMicPressEnd}
          onMouseLeave={handleMicPressEnd}
          onTouchStart={handleMicPressStart}
          onTouchEnd={handleMicPressEnd}
          disabled={!micSupported}
          title={
            !micSupported
              ? "Voice input isn't supported in this browser"
              : pushToTalk
                ? "Hold to talk (or hold Space)"
                : listening
                  ? "Stop listening (or release Space)"
                  : "Speak to Jarvis (or hold Space)"
          }
          className={clsx(
            "flex shrink-0 items-center justify-center rounded-xl border p-2.5 transition select-none",
            !micSupported
              ? "cursor-not-allowed border-jarvis-border/50 text-jarvis-muted/50"
              : listening
                ? "animate-pulseGlow border-jarvis-rose/50 bg-jarvis-rose/10 text-jarvis-rose"
                : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
          )}
        >
          <Mic className="h-4 w-4" />
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={listening ? "Listening..." : "Message Jarvis... (hold Space to talk)"}
          className="flex-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
        />
        <button
          type="submit"
          disabled={sending}
          className="press-scale flex shrink-0 items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-4 py-2.5 text-sm font-medium text-jarvis-cyan transition-all duration-200 hover:bg-jarvis-cyan/20 hover:shadow-glow-sm disabled:opacity-50"
        >
          <CornerDownLeft className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
