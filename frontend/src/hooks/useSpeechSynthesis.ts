import { useCallback, useEffect, useState } from "react";

const MUTE_STORAGE_KEY = "jarvis_speech_muted";

function readStoredMuted(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(MUTE_STORAGE_KEY) === "true";
  } catch {
    // localStorage can throw in locked-down/private-browsing contexts.
    return false;
  }
}

interface UseSpeechSynthesisReturn {
  /** Whether this browser exposes the SpeechSynthesis API. */
  supported: boolean;
  /** Persisted (localStorage) mute setting. */
  muted: boolean;
  toggleMuted: () => void;
  /**
   * Speaks `text` aloud. No-ops silently if unsupported or muted — `onEnd`
   * still fires immediately in that case so callers driving continuous
   * conversation mode (resume listening once Jarvis is done talking)
   * don't need to special-case "nothing was actually spoken."
   */
  speak: (text: string, onEnd?: () => void) => void;
  /** Stops any in-progress speech immediately. */
  cancel: () => void;
  /** True for the duration of an utterance — drives JarvisCore's "speaking" state. */
  speaking: boolean;
}

/**
 * Wrapper around window.speechSynthesis. Mute state is read from and
 * written to localStorage so it survives reloads — required by the voice
 * feature spec, not just a nice-to-have.
 */
export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [muted, setMuted] = useState<boolean>(readStoredMuted);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(MUTE_STORAGE_KEY, String(muted));
    } catch {
      // ignore storage failures — muting still works for this session
    }
  }, [muted]);

  // Stop any speech in flight if the component unmounts.
  useEffect(() => {
    return () => {
      if (supported) window.speechSynthesis.cancel();
    };
  }, [supported]);

  const cancel = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [supported]);

  const speak = useCallback(
    (text: string, onEnd?: () => void) => {
      if (!supported || muted) {
        onEnd?.();
        return;
      }
      const trimmed = text.trim();
      if (!trimmed) {
        onEnd?.();
        return;
      }

      // Cancel whatever's currently queued/speaking so replies don't stack.
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(trimmed);
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.lang = "en-US";
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => {
        setSpeaking(false);
        onEnd?.();
      };
      // A cancelled utterance (barge-in, mute, unmount) still needs to
      // release whoever was waiting on "speech finished" — e.g. continuous
      // conversation mode resuming the mic.
      utterance.onerror = () => {
        setSpeaking(false);
        onEnd?.();
      };
      window.speechSynthesis.speak(utterance);
    },
    [supported, muted]
  );

  const toggleMuted = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      if (next) cancel();
      return next;
    });
  }, [cancel]);

  return { supported, muted, toggleMuted, speak, cancel, speaking };
}
