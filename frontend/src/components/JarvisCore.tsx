import { motion } from "framer-motion";
import clsx from "clsx";

// The AI Core's full state vocabulary — it visually communicates what Jarvis is
// doing. `speaking` is the voice/TTS sub-state.
export type JarvisCoreState =
  | "idle"
  | "listening"
  | "thinking"
  | "researching"
  | "generating"
  | "waiting" // waiting for approval
  | "completed"
  | "speaking";

// `idle` uses the active workspace accent (var, cyan fallback) so the Core
// takes on the current company's color; every other state has a fixed,
// meaning-carrying hue.
const STATE_HUE: Record<JarvisCoreState, { core: string; ring: string; glow: string }> = {
  idle: {
    core: "var(--ws-accent, rgba(45,212,240,0.9))",
    ring: "var(--ws-accent-soft, rgba(45,212,240,0.5))",
    glow: "var(--ws-glow, rgba(45,212,240,0.35))",
  },
  listening: { core: "rgba(244,63,94,0.9)", ring: "rgba(244,63,94,0.55)", glow: "rgba(244,63,94,0.4)" },
  thinking: { core: "rgba(139,92,246,0.9)", ring: "rgba(139,92,246,0.55)", glow: "rgba(139,92,246,0.4)" },
  researching: { core: "rgba(59,130,246,0.95)", ring: "rgba(59,130,246,0.55)", glow: "rgba(59,130,246,0.42)" },
  generating: { core: "rgba(16,185,129,0.95)", ring: "rgba(45,212,240,0.55)", glow: "rgba(16,185,129,0.45)" },
  waiting: { core: "rgba(245,158,11,0.95)", ring: "rgba(245,158,11,0.6)", glow: "rgba(245,158,11,0.45)" },
  completed: { core: "rgba(16,185,129,0.95)", ring: "rgba(16,185,129,0.55)", glow: "rgba(16,185,129,0.4)" },
  speaking: { core: "rgba(45,212,240,1)", ring: "rgba(59,130,246,0.6)", glow: "rgba(45,212,240,0.5)" },
};

// Per-state core-sphere pulse (scale keyframes + duration). Distinct rhythms so
// each state *reads* differently: thinking is quick and tight, researching a
// steady scan-breathe, generating an energetic pump, waiting a slow attention
// swell, completed an almost-still settle.
const PULSE: Record<JarvisCoreState, { scale: number[]; dur: number }> = {
  idle: { scale: [1, 1, 1], dur: 3.2 },
  listening: { scale: [1, 1.04, 1], dur: 1.1 },
  thinking: { scale: [1, 1.12, 1], dur: 0.7 },
  researching: { scale: [1, 1.07, 1], dur: 0.95 },
  generating: { scale: [1, 1.1, 1], dur: 0.5 },
  waiting: { scale: [1, 1.05, 1], dur: 1.6 },
  completed: { scale: [1, 1.02, 1], dur: 1.8 },
  speaking: { scale: [1, 1.06, 1], dur: 1.1 },
};

// Deterministic-looking but varied bar heights for the "speaking" equalizer.
const EQ_DELAYS = [0, 0.12, 0.05, 0.18, 0.08];

const LABEL: Record<JarvisCoreState, string> = {
  idle: "idle",
  listening: "listening",
  thinking: "thinking",
  researching: "researching",
  generating: "generating",
  waiting: "waiting for approval",
  completed: "task complete",
  speaking: "speaking",
};

/**
 * Jarvis's visual "face" — a holographic, state-reactive orb. Colour + motion
 * communicate what Jarvis is doing (idle/listening/thinking/researching/
 * generating/waiting-for-approval/completed/speaking). Pure CSS/SVG + Tailwind
 * animate-* utilities + a few framer scales — no canvas/WebGL, so it stays
 * cheap enough to render inside cards/lists too.
 */
export default function JarvisCore({
  state = "idle",
  size = 96,
  className,
}: {
  state?: JarvisCoreState;
  size?: number;
  className?: string;
}) {
  const hue = STATE_HUE[state];
  const pulse = PULSE[state];
  // Rose sonar rings on listening; a slower amber attention ring while waiting.
  const showRings = state === "listening" || state === "waiting";
  const ringDur = state === "waiting" ? "2.6s" : "1.8s";
  // A bright rotating scan arc while researching/generating — reads as "working."
  const scanning = state === "researching" || state === "generating";

  return (
    <div
      className={clsx("relative shrink-0", className)}
      style={{ width: size, height: size }}
      aria-label={`Jarvis is ${LABEL[state]}`}
      role="img"
    >
      {/* Ambient outer glow */}
      <div
        className="absolute inset-0 rounded-full blur-xl transition-colors duration-700"
        style={{ background: hue.glow }}
      />

      {/* Outer rotating conic ring */}
      <div
        className={clsx("absolute inset-0 rounded-full transition-colors duration-700", scanning ? "animate-spinSlow [animation-duration:6s]" : "animate-spinSlow")}
        style={{
          background: `conic-gradient(from 0deg, transparent 0%, ${hue.ring} 15%, transparent 35%, transparent 65%, ${hue.ring} 85%, transparent 100%)`,
          mask: "radial-gradient(farthest-side, transparent calc(100% - 3px), black calc(100% - 3px))",
          WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 3px), black calc(100% - 3px))",
        }}
      />
      {/* Inner counter-rotating ring, offset inward */}
      <div
        className="absolute animate-spinSlowReverse rounded-full transition-colors duration-700"
        style={{
          inset: size * 0.12,
          background: `conic-gradient(from 90deg, transparent 0%, ${hue.core} 10%, transparent 30%)`,
          mask: "radial-gradient(farthest-side, transparent calc(100% - 2px), black calc(100% - 2px))",
          WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 2px), black calc(100% - 2px))",
          opacity: 0.8,
        }}
      />

      {/* Bright scan arc — researching / generating */}
      {scanning && (
        <div
          className="absolute inset-0 animate-spinSlow rounded-full [animation-duration:1.6s]"
          style={{
            background: `conic-gradient(from 0deg, transparent 0%, ${hue.core} 6%, transparent 14%)`,
            mask: "radial-gradient(farthest-side, transparent calc(100% - 4px), black calc(100% - 4px))",
            WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 4px), black calc(100% - 4px))",
          }}
        />
      )}

      {/* Sonar / attention rings — listening (rose) or waiting (amber) */}
      {showRings &&
        [0, 0.5, 1].map((delay) => (
          <span
            key={delay}
            className="absolute animate-ringExpand rounded-full border"
            style={{
              inset: size * 0.22,
              borderColor: hue.ring,
              animationDelay: `${delay}s`,
              animationDuration: ringDur,
            }}
          />
        ))}

      {/* Core sphere */}
      <motion.div
        className={clsx("absolute rounded-full", state === "idle" && "animate-orbBreathe")}
        style={{
          inset: size * 0.28,
          background: `radial-gradient(circle at 35% 30%, white 0%, ${hue.core} 28%, ${hue.core} 60%, transparent 100%)`,
          boxShadow: `0 0 ${size * (state === "completed" || state === "waiting" ? 0.5 : 0.35)}px ${hue.glow}`,
        }}
        animate={state === "idle" ? { scale: 1 } : { scale: pulse.scale }}
        transition={{ duration: pulse.dur, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Speaking: a small equalizer read-out over the core */}
      {state === "speaking" && (
        <div className="absolute inset-0 flex items-center justify-center gap-[3px]">
          {EQ_DELAYS.map((delay, i) => (
            <span
              key={i}
              className="w-[3px] animate-eqBounce rounded-full bg-white/90"
              style={{ height: size * 0.22, animationDelay: `${delay}s` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
