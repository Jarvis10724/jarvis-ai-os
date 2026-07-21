import { useState, type FormEvent } from "react";
import { AlertTriangle, Loader2, Mic, MicOff, Send, SlidersHorizontal, Smartphone, Volume2, VolumeX } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import clsx from "clsx";

import { activeMicLabel, isIPhoneMic, type useMicrophoneDevices } from "@/hooks/useMicrophoneDevices";
import type { useVoiceOrb } from "@/hooks/useVoiceOrb";

type Voice = ReturnType<typeof useVoiceOrb>;
type MicDevices = ReturnType<typeof useMicrophoneDevices>;

const STATE_META: Record<
  Voice["state"],
  { label: string; dot: string; tone: string }
> = {
  offline: { label: "Voice offline", dot: "bg-jarvis-muted", tone: "text-jarvis-muted" },
  insecure: { label: "Voice needs HTTPS", dot: "bg-jarvis-amber", tone: "text-jarvis-amber" },
  "mic-unavailable": { label: "No microphone", dot: "bg-jarvis-amber", tone: "text-jarvis-amber" },
  "permission-denied": { label: "Mic blocked", dot: "bg-jarvis-rose", tone: "text-jarvis-rose" },
  idle: { label: "Ready", dot: "bg-jarvis-emerald", tone: "text-jarvis-emerald" },
  listening: { label: "Listening", dot: "bg-jarvis-rose", tone: "text-jarvis-rose" },
  transcribing: { label: "Transcribing", dot: "bg-jarvis-violet", tone: "text-jarvis-violet" },
  thinking: { label: "Thinking", dot: "bg-jarvis-violet", tone: "text-jarvis-violet" },
  speaking: { label: "Speaking", dot: "bg-jarvis-cyan", tone: "text-jarvis-cyan" },
  error: { label: "Error", dot: "bg-jarvis-rose", tone: "text-jarvis-rose" },
};

// A compact live waveform: fixed bars whose heights ride the current level
// with a little per-bar variance so it reads as audio, not a single meter.
function Waveform({ level, active }: { level: number; active: boolean }) {
  const bars = [0.4, 0.7, 1, 0.6, 0.85, 0.5, 0.9, 0.65, 0.35];
  return (
    <div className="flex h-6 items-center gap-[3px]">
      {bars.map((mult, i) => (
        <span
          key={i}
          className="w-[3px] rounded-full bg-jarvis-rose transition-[height] duration-75"
          style={{ height: `${Math.max(3, (active ? level : 0) * mult * 24 + 3)}px` }}
        />
      ))}
    </div>
  );
}

/**
 * The floating voice console — the ground-truth readout for the AI Core's
 * voice control, plus the always-available text-command fallback. Slides up
 * from the bottom; auto-expands when voice is active, and can be opened
 * manually to type. Never renders a secret — it only reflects engine state.
 */
export default function VoiceConsole({
  voice,
  mic,
  onOpenDiagnostics,
}: {
  voice: Voice;
  mic: MicDevices;
  onOpenDiagnostics: () => void;
}) {
  const [text, setText] = useState("");
  const meta = STATE_META[voice.state];
  const listening = voice.state === "listening";
  const busy = voice.state === "thinking" || voice.state === "transcribing";

  const activeLabel = activeMicLabel(mic.devices, mic.selectedId);
  const activeIsIPhone = isIPhoneMic(activeLabel);
  // Only surface a specific input in the compact bar (default input is implied
  // by "Ready"); keeps the console uncluttered while making a chosen mic —
  // like an iPhone Continuity mic — clearly visible.
  const showActiveMic = !!mic.selectedId;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    voice.sendText(text);
    setText("");
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-[max(1rem,env(safe-area-inset-bottom))] z-30 flex justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="hud-panel hud-corner pointer-events-auto w-full max-w-2xl p-3"
      >
        <div className="flex items-center gap-3">
          {/* State pill */}
          <div className="flex shrink-0 items-center gap-2">
            <span className={clsx("h-2 w-2 shrink-0 animate-pulseGlow rounded-full", meta.dot)} />
            <span className={clsx("text-xs font-semibold uppercase tracking-wider", meta.tone)}>{meta.label}</span>
          </div>

          {/* Active mic chip — visible whenever a specific input is selected. */}
          {showActiveMic && (
            <span
              className="hidden max-w-[10rem] shrink-0 items-center gap-1 rounded-lg border border-jarvis-border/70 bg-jarvis-panel2/50 px-2 py-1 text-[10px] text-jarvis-muted md:flex"
              title={`Active microphone: ${activeLabel}`}
            >
              {activeIsIPhone ? (
                <Smartphone className="h-3 w-3 shrink-0 text-jarvis-cyan" />
              ) : (
                <Mic className="h-3 w-3 shrink-0 text-jarvis-cyan" />
              )}
              <span className="truncate">{activeIsIPhone ? "iPhone Mic" : activeLabel}</span>
            </span>
          )}

          {/* Live waveform while listening */}
          {listening && <Waveform level={voice.level} active />}
          {busy && <Loader2 className="h-4 w-4 animate-spin text-jarvis-violet" />}

          {/* Text fallback */}
          <form onSubmit={submit} className="flex flex-1 items-center gap-2">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={listening ? (voice.interim || "Listening…") : "Type a command, or tap the core to talk…"}
              className="min-w-0 flex-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!text.trim()}
              className="press-scale flex shrink-0 items-center justify-center rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 p-2 text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
              title="Send command"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>

          {/* Push-to-talk */}
          <button
            onClick={voice.toggle}
            disabled={!voice.available}
            title={voice.available ? "Push to talk (or hold Space)" : "Voice input unavailable"}
            className={clsx(
              "press-scale flex shrink-0 items-center justify-center rounded-xl border p-2 transition",
              !voice.available
                ? "cursor-not-allowed border-jarvis-border/50 text-jarvis-muted/50"
                : listening
                  ? "animate-pulseGlow border-jarvis-rose/50 bg-jarvis-rose/10 text-jarvis-rose"
                  : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
            )}
          >
            {voice.available ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
          </button>

          {/* Mute + diagnostics */}
          <button
            onClick={voice.toggleMuted}
            title={voice.muted ? "Unmute Jarvis's voice" : "Mute Jarvis's voice"}
            className={clsx(
              "press-scale hidden shrink-0 rounded-xl border p-2 transition sm:flex",
              voice.muted
                ? "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted hover:text-jarvis-text"
                : "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
            )}
          >
            {voice.muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
          <button
            onClick={onOpenDiagnostics}
            title="Microphone diagnostics"
            className="press-scale shrink-0 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 p-2 text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
          >
            <SlidersHorizontal className="h-4 w-4" />
          </button>
        </div>

        {/* Detail line: errors, transcript, and last reply. */}
        <AnimatePresence>
          {(voice.detail || voice.lastReplyText || voice.interim) && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-2 border-t border-jarvis-border/50 pt-2 text-xs">
                {["offline", "insecure", "mic-unavailable", "permission-denied", "error"].includes(voice.state) &&
                  voice.detail && (
                    <p className="flex items-start gap-1.5 text-jarvis-amber">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      {voice.detail}
                    </p>
                  )}
                {voice.interim && listening && <p className="text-jarvis-muted">“{voice.interim}”</p>}
                {voice.lastUserText && !listening && (
                  <p className="text-jarvis-muted">
                    <span className="text-jarvis-faint">You:</span> {voice.lastUserText}
                  </p>
                )}
                {voice.lastReplyText && !listening && (
                  <p className="mt-1 text-jarvis-text">
                    <span className="text-jarvis-cyan">Jarvis:</span> {voice.lastReplyText}
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
