import clsx from "clsx";

import JarvisCore, { type JarvisCoreState } from "@/components/JarvisCore";
import OrbitRing from "@/components/orbital/OrbitRing";
import ParticleField from "@/components/orbital/ParticleField";

/**
 * The AI Core — the visual and navigational center of the shell, and Jarvis's
 * primary voice button. A layered energy core: an ambient bloom that swells
 * softly while idle and quickens while processing, several concentric rings,
 * expanding pulse rings, a twinkling particle field, an audio-reactive ring
 * that scales with live mic level while listening, and the voice-reactive
 * JarvisCore orb at the center. Everything is CSS/transform-driven for
 * performance — no canvas, no per-frame JS beyond the (throttled) level.
 */
export default function OrbitalCore({
  diameter,
  state,
  title,
  subtitle,
  hint,
  level = 0,
  onClick,
}: {
  diameter: number;
  state: JarvisCoreState;
  title: string;
  subtitle: string;
  /** Small helper line under the subtitle (e.g. "Tap or hold Space to talk"). */
  hint?: string;
  /** Live 0..1 mic level; scales the audio-reactive ring while listening. */
  level?: number;
  /** Makes the core an interactive push-to-talk button. */
  onClick?: () => void;
}) {
  const orbSize = diameter * 0.42;
  const active = state !== "idle";
  const listening = state === "listening";
  // Audio-reactive scale for the innermost reactive ring.
  const reactiveScale = 1 + (listening ? level * 0.45 : 0);

  return (
    <div
      className="pointer-events-none absolute left-1/2 top-1/2 flex items-center justify-center"
      style={{ width: diameter, height: diameter, transform: "translate(-50%, -50%)" }}
    >
      {/* Ambient energy bloom — two stacked blurred radials. */}
      <div
        className={clsx(
          "absolute left-1/2 top-1/2 rounded-full blur-3xl",
          active ? "animate-coreBloomActive bg-jarvis-cyan/25" : "animate-coreBloom bg-jarvis-cyan/15"
        )}
        style={{ width: diameter * 0.95, height: diameter * 0.95 }}
      />
      <div
        className={clsx(
          "absolute left-1/2 top-1/2 rounded-full blur-2xl",
          active ? "animate-coreBloomActive bg-jarvis-blue/20" : "animate-coreBloom bg-jarvis-violet/10"
        )}
        style={{ width: diameter * 0.55, height: diameter * 0.55, animationDelay: "0.4s" }}
      />

      {/* Expanding energy pulse rings. */}
      {[0, 1.1, 2.2].map((delay, idx) => (
        <span
          key={delay}
          className="absolute left-1/2 top-1/2 rounded-full border border-jarvis-cyan/40 animate-corePulseRing"
          style={{
            width: diameter * 0.66,
            height: diameter * 0.66,
            animationDelay: `${delay}s`,
            animationDuration: active ? "2.2s" : "3.4s",
            display: !active && idx > 0 ? "none" : undefined,
          }}
        />
      ))}

      {/* Concentric structural rings. */}
      <OrbitRing diameter={diameter} durationSec={active ? 24 : 46} opacity={0.3} />
      <OrbitRing diameter={diameter * 0.9} durationSec={active ? 30 : 58} reverse opacity={0.18} />
      <OrbitRing diameter={diameter * 0.82} durationSec={active ? 18 : 34} opacity={0.24} />
      <OrbitRing diameter={diameter * 0.66} durationSec={active ? 34 : 60} reverse dashed={false} opacity={0.2} />
      <OrbitRing diameter={diameter * 0.52} durationSec={active ? 22 : 44} opacity={0.14} />

      {/* Audio-reactive ring — expands with live mic level while listening. */}
      <div
        className="absolute left-1/2 top-1/2 rounded-full border-2 border-jarvis-rose/50"
        style={{
          width: diameter * 0.46,
          height: diameter * 0.46,
          transform: `translate(-50%, -50%) scale(${reactiveScale})`,
          opacity: listening ? 0.35 + level * 0.5 : 0,
          transition: "transform 0.08s linear, opacity 0.2s ease",
          boxShadow: listening ? `0 0 ${18 + level * 40}px rgba(244,63,94,0.4)` : "none",
        }}
      />

      {/* Twinkling particle field. */}
      <ParticleField diameter={diameter * 0.98} count={24} active={active} />

      {/* Brighter tracer particles. */}
      <div
        className="absolute animate-spin"
        style={{ width: diameter, height: diameter, animationDuration: active ? "9s" : "18s" }}
      >
        <span className="absolute left-1/2 top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-jarvis-cyan shadow-glow-sm" />
      </div>
      <div
        className="absolute animate-spin"
        style={{ width: diameter * 0.82, height: diameter * 0.82, animationDuration: active ? "13s" : "26s", animationDirection: "reverse" }}
      >
        <span className="absolute left-1/2 top-0 h-1 w-1 -translate-x-1/2 rounded-full bg-jarvis-blue shadow-glow-sm" />
      </div>

      {/* The clickable push-to-talk hit area, sized to the orb. Keeps the rest
          of the core decorative (pointer-events-none) while this one target is
          interactive. */}
      {onClick ? (
        <button
          type="button"
          onClick={onClick}
          aria-label="Talk to Jarvis — push to talk"
          className="press-scale pointer-events-auto absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-jarvis-cyan/60"
          style={{ width: orbSize * 1.1, height: orbSize * 1.1 }}
        >
          <JarvisCore state={state} size={orbSize} />
        </button>
      ) : (
        <JarvisCore state={state} size={orbSize} />
      )}

      <div className="pointer-events-none absolute bottom-[6%] left-1/2 w-full -translate-x-1/2 text-center">
        <p className="font-display text-sm font-bold tracking-[0.3em] text-jarvis-text text-glow sm:text-base">
          {title}
        </p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.25em] text-jarvis-muted sm:text-xs">{subtitle}</p>
        {hint && (
          <p className="mt-1.5 text-[10px] uppercase tracking-[0.2em] text-jarvis-faint">{hint}</p>
        )}
      </div>
    </div>
  );
}
