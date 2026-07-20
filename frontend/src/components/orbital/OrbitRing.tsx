import clsx from "clsx";

/**
 * A single decorative concentric ring around the AI Core. Pure CSS —
 * dashed/dotted circle rotating slowly, direction and speed set per
 * instance so the whole core reads as several independent layers of
 * machinery rather than one spinning texture.
 */
export default function OrbitRing({
  diameter,
  durationSec,
  reverse = false,
  dashed = true,
  opacity = 0.3,
  className,
}: {
  diameter: number;
  durationSec: number;
  reverse?: boolean;
  dashed?: boolean;
  opacity?: number;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "pointer-events-none absolute rounded-full border-jarvis-cyan/40",
        dashed ? "border border-dashed" : "border",
        reverse ? "animate-spinSlowReverse" : "animate-spinSlow",
        className
      )}
      style={{
        width: diameter,
        height: diameter,
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
        animationDuration: `${durationSec}s`,
        opacity,
      }}
    />
  );
}
