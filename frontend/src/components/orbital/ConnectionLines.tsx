import { useId } from "react";

interface Point {
  x: number;
  y: number;
}

/**
 * Glowing vector lines from the AI Core to every visible orbital node — an
 * SVG overlay sized to match the container exactly so endpoints line up
 * pixel-for-pixel with the (already-computed) node centers. Each line has a
 * soft blurred "glow" copy underneath a crisp animated dashed stroke, so the
 * links read as luminous energy conduits rather than flat hairlines. When
 * `active` (Jarvis processing), the flow speeds up and brightens.
 */
export default function ConnectionLines({
  width,
  height,
  origin,
  points,
  active = false,
}: {
  width: number;
  height: number;
  origin: Point;
  points: Point[];
  active?: boolean;
}) {
  const filterId = useId();
  const gradId = useId();
  if (!width || !height) return null;

  return (
    <svg
      className="pointer-events-none absolute inset-0"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
    >
      <defs>
        <filter id={filterId} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient
          id={gradId}
          gradientUnits="userSpaceOnUse"
          cx={origin.x}
          cy={origin.y}
          r={Math.max(width, height) / 2}
        >
          <stop offset="0%" stopColor="rgb(var(--jarvis-cyan))" stopOpacity="0.9" />
          <stop offset="100%" stopColor="rgb(var(--jarvis-blue))" stopOpacity="0.45" />
        </radialGradient>
      </defs>

      {/* Soft glow underlay — solid, blurred, low opacity. */}
      <g filter={`url(#${filterId})`} opacity={active ? 0.5 : 0.28}>
        {points.map((p, i) => (
          <line
            key={`glow-${i}`}
            x1={origin.x}
            y1={origin.y}
            x2={p.x}
            y2={p.y}
            stroke={`url(#${gradId})`}
            strokeWidth={active ? 2 : 1.4}
            strokeLinecap="round"
          />
        ))}
      </g>

      {/* Crisp animated dashed flow on top. */}
      {points.map((p, i) => (
        <line
          key={i}
          x1={origin.x}
          y1={origin.y}
          x2={p.x}
          y2={p.y}
          className={active ? "connection-line connection-line--active" : "connection-line"}
          stroke="rgb(var(--jarvis-cyan))"
          strokeWidth={1}
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}
