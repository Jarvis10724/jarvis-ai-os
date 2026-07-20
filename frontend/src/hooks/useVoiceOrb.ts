import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/api/client";
import { useAudioLevel } from "@/hooks/useAudioLevel";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import type { JarvisCoreState } from "@/components/JarvisCore";
import type { ChatMessage } from "@/types";

// Every state the voice orb can be in — a superset of JarvisCoreState with
// the extra lifecycle/error states the spec asks to surface explicitly.
export type VoiceState =
  | "offline" // speech recognition unavailable in this browser
  | "insecure" // page isn't a secure context (needs https/localhost)
  | "mic-unavailable" // no microphone / audio API
  | "permission-denied" // user blocked mic access
  | "idle" // ready, waiting
  | "listening" // capturing + live level
  | "transcribing" // stopped capture, resolving final transcript
  | "thinking" // waiting on Jarvis's reply
  | "speaking" // reading the reply aloud
  | "error"; // request or engine error

// Which of the above map onto JarvisCore's 4 animation states (for the orb
// and the global sidebar indicator).
export function toCoreState(v: VoiceState): JarvisCoreState {
  switch (v) {
    case "listening":
      return "listening";
    case "transcribing":
    case "thinking":
      return "thinking";
    case "speaking":
      return "speaking";
    default:
      return "idle";
  }
}

const PERSONA_STORAGE_KEY = "jarvis_active_persona";

interface UseVoiceOrbArgs {
  companyId: string | null;
  /** Push mapped state to the global sidebar orb (AssistantStatusContext). */
  onStateChange?: (core: JarvisCoreState) => void;
  /**
   * Preferred input device id ("" / undefined = OS default). Pins the live
   * audio-level meter to this device (e.g. an iPhone Continuity mic). Note:
   * browser speech recognition itself can't be pinned and always follows the
   * OS/site default input — the level meter is what reflects this choice.
   */
  deviceId?: string;
}

interface UseVoiceOrbReturn {
  state: VoiceState;
  /** 0..1 live mic level while listening. */
  level: number;
  /** Live (not-yet-final) transcript while speaking. */
  interim: string;
  /** The last thing the user said. */
  lastUserText: string;
  /** The last thing Jarvis replied. */
  lastReplyText: string;
  /** Human-readable error/status detail for the current state, if any. */
  detail: string | null;
  /** Push-to-talk toggle: start if idle, stop if listening. */
  toggle: () => void;
  /** Explicit stop (used by keyboard release). */
  stop: () => void;
  /** Text fallback — send a typed command through the same pipeline. */
  sendText: (text: string) => void;
  /** Whether voice input is usable at all in this environment. */
  available: boolean;
  // Diagnostics
  micSupported: boolean;
  recognitionSupported: boolean;
  secureContext: boolean;
  muted: boolean;
  toggleMuted: () => void;
}

const DETAIL: Partial<Record<VoiceState, string>> = {
  offline: "Voice recognition isn't available in this browser. Use Chrome, Edge, or Safari — or type below.",
  insecure: "Voice needs a secure context (https or localhost). Type your command below instead.",
  "mic-unavailable": "No microphone was detected. Connect one, or type your command below.",
  "permission-denied": "Microphone access was blocked. Allow it in your browser's site settings, then try again.",
  transcribing: "Transcribing…",
  thinking: "Jarvis is thinking…",
  speaking: "Jarvis is responding…",
};

/**
 * The engine behind the AI Core acting as Jarvis's voice button. Combines a
 * live audio-level meter (useAudioLevel), browser speech recognition
 * (useSpeechRecognition), speech synthesis (useSpeechSynthesis) and the chat
 * API into one push-to-talk state machine. Single-utterance per turn: press
 * to talk, press again (or release the key) to send. No wake word, no
 * always-on listening — capture only happens between an explicit start and
 * stop. No secrets touch this layer; it calls the same authenticated /chat
 * endpoint the text UI uses.
 */
export function useVoiceOrb({ companyId, onStateChange, deviceId }: UseVoiceOrbArgs): UseVoiceOrbReturn {
  const [phase, setPhase] = useState<VoiceState>("idle");
  const [lastUserText, setLastUserText] = useState("");
  const [lastReplyText, setLastReplyText] = useState("");
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  const { supported: micSupported, active: audioActive, level, error: audioError, start: startAudio, stop: stopAudio } =
    useAudioLevel();
  const { supported: ttsSupported, muted, toggleMuted, speak, cancel: cancelSpeech } = useSpeechSynthesis();

  const handledFinalRef = useRef(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const persona = (() => {
    try {
      return localStorage.getItem(PERSONA_STORAGE_KEY) || "ceo_assistant";
    } catch {
      return "ceo_assistant";
    }
  })();

  const runChat = useCallback(
    async (text: string) => {
      setLastUserText(text);
      setPhase("thinking");
      try {
        const messages: ChatMessage[] = [{ role: "user", content: text }];
        const res = await api.chat(messages, companyId, persona);
        setLastReplyText(res.text);
        setPhase("speaking");
        speak(res.text, () => setPhase("idle"));
      } catch (err) {
        setErrorDetail(
          err instanceof ApiError ? err.message : "Couldn't reach Jarvis. Check the AI provider key in .env."
        );
        setPhase("error");
      }
    },
    [companyId, persona, speak]
  );

  const {
    supported: recognitionSupported,
    listening,
    error: voiceError,
    interimTranscript,
    start: startRecognition,
    stop: stopRecognition,
  } = useSpeechRecognition({
    onFinalResult: (transcript) => {
      handledFinalRef.current = true;
      stopAudio();
      if (transcript.trim()) runChat(transcript.trim());
      else setPhase("idle");
    },
  });

  const secureContext = typeof window !== "undefined" && window.isSecureContext === true;
  const available = recognitionSupported && micSupported && secureContext;

  // Resolve the current display state from the engine signals. Recognition/
  // audio errors take priority so the user always sees why it isn't working.
  const state: VoiceState = (() => {
    if (!recognitionSupported) return "offline";
    if (!secureContext) return "insecure";
    if (!micSupported) return "mic-unavailable";
    if (audioError === "permission-denied" || voiceError === "not-allowed") return "permission-denied";
    if (audioError === "no-device" || voiceError === "audio-capture") return "mic-unavailable";
    if (phase === "error") return "error";
    if (listening || audioActive) return "listening";
    return phase; // idle | transcribing | thinking | speaking
  })();

  const detail = state === "error" ? errorDetail : DETAIL[state] ?? null;

  // Mirror to the global sidebar orb.
  useEffect(() => {
    onStateChange?.(toCoreState(state));
  }, [state, onStateChange]);

  const start = useCallback(async () => {
    if (!available) return;
    setErrorDetail(null);
    handledFinalRef.current = false;
    cancelSpeech(); // barge-in: interrupt any in-progress reply
    // Pin the live meter to the chosen device (read fresh each start, so a
    // selection change applies on the next listen without an app restart).
    const ok = await startAudio(deviceId || undefined);
    if (!ok) return; // audioError drives the visible state
    startRecognition();
  }, [available, cancelSpeech, startAudio, startRecognition, deviceId]);

  const stop = useCallback(() => {
    if (!listening) return;
    // Show "transcribing" until the final result lands (or recognition ends).
    if (!handledFinalRef.current) setPhase("transcribing");
    stopRecognition();
  }, [listening, stopRecognition]);

  const toggle = useCallback(() => {
    if (listening || audioActive) stop();
    else if (["idle", "error", "speaking"].includes(phaseRef.current) || available) start();
  }, [listening, audioActive, stop, start, available]);

  const sendText = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      cancelSpeech();
      runChat(trimmed);
    },
    [cancelSpeech, runChat]
  );

  // If recognition ends without a final transcript (e.g. silence), fall back
  // to idle and release the mic rather than hanging on "transcribing".
  useEffect(() => {
    if (!listening && phase === "transcribing" && !handledFinalRef.current) {
      const t = setTimeout(() => {
        if (!handledFinalRef.current) {
          stopAudio();
          setPhase("idle");
        }
      }, 1500);
      return () => clearTimeout(t);
    }
  }, [listening, phase, stopAudio]);

  // Release the mic on unmount.
  useEffect(() => () => stopAudio(), [stopAudio]);

  return {
    state,
    level,
    interim: interimTranscript,
    lastUserText,
    lastReplyText,
    detail,
    toggle,
    stop,
    sendText,
    available,
    micSupported,
    recognitionSupported,
    secureContext,
    muted: ttsSupported ? muted : true,
    toggleMuted,
  };
}
