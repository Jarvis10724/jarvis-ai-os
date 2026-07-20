import { useCallback, useEffect, useRef, useState } from "react";

export type SpeechRecognitionErrorKind =
  | "not-allowed"
  | "audio-capture"
  | "no-speech"
  | "unsupported"
  | "other";

interface UseSpeechRecognitionOptions {
  /** Called once per utterance, with the final recognized transcript. */
  onFinalResult: (transcript: string) => void;
}

interface UseSpeechRecognitionReturn {
  /** Whether this browser exposes SpeechRecognition at all. */
  supported: boolean;
  /** True while actively listening for speech. */
  listening: boolean;
  /** Last error, cleared automatically the next time listening starts. */
  error: SpeechRecognitionErrorKind | null;
  /** Live, not-yet-final transcript — useful for a "Listening..." preview. */
  interimTranscript: string;
  start: () => void;
  stop: () => void;
}

function getRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/**
 * Thin wrapper around the browser's SpeechRecognition API for
 * push-to-talk-style, single-utterance dictation: click to start, speak,
 * and `onFinalResult` fires once recognition settles on a final transcript.
 */
export function useSpeechRecognition({
  onFinalResult,
}: UseSpeechRecognitionOptions): UseSpeechRecognitionReturn {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<SpeechRecognitionErrorKind | null>(null);
  const [interimTranscript, setInterimTranscript] = useState("");

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const onFinalResultRef = useRef(onFinalResult);
  onFinalResultRef.current = onFinalResult;

  const supported = getRecognitionConstructor() !== null;

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  const start = useCallback(() => {
    const RecognitionCtor = getRecognitionConstructor();
    setError(null);
    setInterimTranscript("");

    if (!RecognitionCtor) {
      setError("unsupported");
      return;
    }

    // Guard against a stray double-click while already listening.
    if (recognitionRef.current) return;

    const recognition = new RecognitionCtor();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = "";
      let interimText = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcriptPiece = result[0]?.transcript ?? "";
        if (result.isFinal) finalText += transcriptPiece;
        else interimText += transcriptPiece;
      }

      if (interimText) setInterimTranscript(interimText);
      if (finalText.trim()) {
        setInterimTranscript("");
        onFinalResultRef.current(finalText.trim());
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setError("not-allowed");
      } else if (event.error === "audio-capture") {
        setError("audio-capture");
      } else if (event.error === "no-speech") {
        setError("no-speech");
      } else {
        setError("other");
      }
    };

    recognition.onend = () => {
      setListening(false);
      setInterimTranscript("");
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
      setListening(true);
    } catch {
      // start() throws if called while already started, or if the
      // underlying platform rejects it outright.
      setError("other");
      setListening(false);
      recognitionRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  return { supported, listening, error, interimTranscript, start, stop };
}
