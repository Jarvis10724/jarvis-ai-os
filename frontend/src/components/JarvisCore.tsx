import { motion } from "framer-motion";
import clsx from "clsx";

export type JarvisCoreState = "idle" | "listening" | "thinking" | "speaking";

const STATE_HUE: Record<JarvisCoreState, { core: string; ring: string; glow: string }> = {
  idle: { core: "rgba(45,212,240,0.9)", ring: "rgba(45,212,240,0.5)", glow: "rgba(45,212,240,0.35)" },
  listening: { core: "rgba(244,63,94,0.9)", ring: "rgba(244,63,94,0.55)", glow: "rgba(244,63,94,0.4)" },
  thinking: { core: "rgba(139,92,246,0.9)", ring: "rgba(139,92,246,0.55)", glow: "rgba(139,92,246,0.4)" },
  speaking: { core: "rgba(45,212,240,1)", ring: "rgba(59,130,246,0.6)", glow: "rgba(45,212,240,0.5)" },
};

// Deterministic-looking but varied bar heights for the "speaking" equalizer —
// avoids everything bouncing in perfect unison, which would read as fake.
const EQ_DELAYS = [0, 0.12, 0.05, 0.18, 0.08];

/**
 * Jarvis's visual "face" — a holographic, voice-reactive orb rather than a
 * static logo. Four states drive both color and motion:
 *   idle      — slow cyan breathing, the resting/ambient state.
 *   listening — rose rings pulsing outward, like sonar picking up your voice.
 *   thinking  — violet, faster inner pulse while waiting on the AI provider.
 *   speaking  — cyan/blue with an animated equalizer, while TTS is playing.
 * Pure CSS/SVG + Tailwind's animate-* utilities (see tailwind.config.js) —
 * no canvas/WebGL, so it stays cheap to render inside cards/lists too.
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

  return (
    <div
      className={clsx("relative shrink-0", className)}
      style={{ width: size, height: size }}
      aria-label={`Jarvis is ${state}`}
      role="img"
    >
      {/* Ambient outer glow */}
      <div
        className="absolute inset-0 rounded-full blur-xl transition-colors duration-700"
        style={{ background: hue.glow }}
      />

      {/* Outer rotating conic ring */}
      <div
        className="absolute inset-0 animate-spinSlow rounded-full transition-colors duration-700"
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

      {/* Listening: sonar rings pushing outward */}
      {state === "listening" &&
        [0, 0.5, 1].map((delay) => (
          <span
            key={delay}
            className="absolute animate-ringExpand rounded-full border"
            style={{ inset: size * 0.22, borderColor: hue.ring, animationDelay: `${delay}s` }}
          />
        ))}

      {/* Core sphere */}
      <motion.div
        className={clsx("absolute rounded-full", state === "idle" && "animate-orbBreathe")}
        style={{
          inset: size * 0.28,
          background: `radial-gradient(circle at 35% 30%, white 0%, ${hue.core} 28%, ${hue.core} 60%, transparent 100%)`,
          boxShadow: `0 0 ${size * 0.35}px ${hue.glow}`,
        }}
        animate={
          state === "thinking"
            ? { scale: [1, 1.12, 1] }
            : state === "speaking"
              ? { scale: [1, 1.06, 1] }
              : { scale: 1 }
        }
        transition={{ duration: state === "thinking" ? 0.7 : 1.1, repeat: Infinity, ease: "easeInOut" }}
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
