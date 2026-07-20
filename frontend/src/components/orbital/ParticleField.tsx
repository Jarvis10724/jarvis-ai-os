import { useMemo } from "react";

// Deterministic pseudo-random so the field is stable across renders (no
// layout jitter, no hydration mismatch) while still looking scattered. A
// tiny LCG seeded by index — cheap and repeatable.
function seeded(i: number): number {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/**
 * Ambient particle field around the AI Core. Each particle rides an
 * invisible orbit ring (a full-size wrapper that slowly rotates), sitting at
 * its own radius/angle, twinkling on its own cadence. Pure CSS transforms —
 * no canvas, no per-frame JS — so it stays cheap even with a few dozen
 * particles. `active` speeds the orbits up while Jarvis is processing.
 */
export default function ParticleField({
  diameter,
  count = 22,
  active = false,
}: {
  diameter: number;
  count?: number;
  active?: boolean;
}) {
  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const radius = (0.32 + seeded(i) * 0.66) * (diameter / 2);
        const angle = seeded(i + 100) * 360;
        const size = 1 + seeded(i + 200) * 2.5;
        const orbit = (26 + seeded(i + 300) * 40) / (active ? 2.4 : 1);
        const reverse = seeded(i + 400) > 0.5;
        const twinkle = 2 + seeded(i + 500) * 3;
        const isBlue = seeded(i + 600) > 0.6;
        return { radius, angle, size, orbit, reverse, twinkle, isBlue, i };
      }),
    [diameter, count, active]
  );

  return (
    <div
      className="pointer-events-none absolute left-1/2 top-1/2"
      style={{ width: diameter, height: diameter, transform: "translate(-50%, -50%)" }}
      aria-hidden="true"
    >
      {particles.map((p) => (
        <div
          key={p.i}
          className="absolute left-1/2 top-1/2"
          style={{
            width: p.radius * 2,
            height: p.radius * 2,
            transform: "translate(-50%, -50%)",
            animation: `${p.reverse ? "spinSlowReverse" : "spinSlow"} ${p.orbit}s linear infinite`,
          }}
        >
          <span
            className="core-particle"
            style={{
              width: p.size,
              height: p.size,
              left: "50%",
              top: 0,
              marginLeft: -p.size / 2,
              transform: `rotate(${p.angle}deg)`,
              transformOrigin: `${p.size / 2}px ${p.radius}px`,
              animationDuration: `${p.twinkle}s`,
              background: p.isBlue ? "rgb(var(--jarvis-blue))" : "rgb(var(--jarvis-cyan))",
            }}
          />
        </div>
      ))}
    </div>
  );
}
