import { useCallback, useEffect, useRef, useState } from "react";

export type AudioLevelError =
  | "unsupported" // no getUserMedia / AudioContext in this browser
  | "insecure" // not a secure context (needs https or localhost)
  | "permission-denied" // user blocked the mic
  | "no-device" // no microphone found
  | "other";

interface UseAudioLevelReturn {
  /** getUserMedia + AudioContext both available in a secure context. */
  supported: boolean;
  /** True while a live mic stream is open and being sampled. */
  active: boolean;
  /** Smoothed input loudness, 0..1, updated ~15×/sec (for the meter/waveform). */
  level: number;
  /** Last error, if start() failed. */
  error: AudioLevelError | null;
  /**
   * Opens the mic (optionally pinned to deviceId) and starts sampling its
   * loudness via a Web Audio AnalyserNode. Resolves true on success. Unlike
   * the old device-priming code, the stream is KEPT OPEN so there's genuine
   * live feedback while listening.
   */
  start: (deviceId?: string) => Promise<boolean>;
  /** Stops sampling, closes the stream + audio context, releases the mic. */
  stop: () => void;
}

function isSecure(): boolean {
  if (typeof window === "undefined") return false;
  // Web Audio + getUserMedia require a secure context: https, or localhost.
  return window.isSecureContext === true;
}

/**
 * Live microphone input-level meter built on the Web Audio API. This is the
 * piece the earlier voice attempt lacked: the old code opened the mic only
 * to read device labels and immediately stopped the stream, so there was no
 * way to see that audio was actually being captured. Here the stream stays
 * open while listening and an AnalyserNode yields a real, smoothed RMS level
 * that drives the orb's audio-reactive animation and the diagnostic meter.
 */
export function useAudioLevel(): UseAudioLevelReturn {
  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof (window.AudioContext || (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext) !==
      "undefined";

  const [active, setActive] = useState(false);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<AudioLevelError | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastEmitRef = useRef(0);

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (ctxRef.current && ctxRef.current.state !== "closed") {
      ctxRef.current.close().catch(() => {});
    }
    ctxRef.current = null;
    setActive(false);
    setLevel(0);
  }, []);

  const start = useCallback(
    async (deviceId?: string): Promise<boolean> => {
      setError(null);
      if (!supported) {
        setError("unsupported");
        return false;
      }
      if (!isSecure()) {
        setError("insecure");
        return false;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: deviceId ? { deviceId: { exact: deviceId } } : true,
        });
        streamRef.current = stream;

        const Ctor =
          window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new Ctor();
        ctxRef.current = ctx;
        // AudioContext often starts "suspended" until a user gesture — the
        // click that triggered start() is one, so resume() here is what makes
        // the analyser actually receive samples (otherwise the level sits at 0).
        if (ctx.state === "suspended") {
          await ctx.resume().catch(() => {});
        }
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.7;
        source.connect(analyser);

        const data = new Uint8Array(analyser.frequencyBinCount);
        const sample = () => {
          analyser.getByteTimeDomainData(data);
          // RMS around the 128 midpoint → 0..1-ish, then gentle boost so quiet
          // speech still reads on the meter without clipping loud speech.
          let sumSq = 0;
          for (let i = 0; i < data.length; i++) {
            const v = (data[i] - 128) / 128;
            sumSq += v * v;
          }
          const rms = Math.sqrt(sumSq / data.length);
          const boosted = Math.min(1, rms * 2.4);
          const now = performance.now();
          if (now - lastEmitRef.current > 66) {
            // ~15fps state updates — smooth enough for a meter, cheap enough
            // to not thrash React.
            lastEmitRef.current = now;
            setLevel(boosted);
          }
          rafRef.current = requestAnimationFrame(sample);
        };
        rafRef.current = requestAnimationFrame(sample);
        setActive(true);
        return true;
      } catch (err) {
        const name = err instanceof DOMException ? err.name : "";
        if (name === "NotAllowedError" || name === "SecurityError") setError("permission-denied");
        else if (name === "NotFoundError" || name === "OverconstrainedError") setError("no-device");
        else setError("other");
        stop();
        return false;
      }
    },
    [supported, stop]
  );

  useEffect(() => stop, [stop]);

  return { supported, active, level, error, start, stop };
}
