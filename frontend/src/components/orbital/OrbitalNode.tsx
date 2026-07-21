import { forwardRef } from "react";
import { motion } from "framer-motion";
import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

export type OrbitalTone = "cyan" | "blue" | "violet" | "amber" | "emerald" | "rose";

export const TONE_STYLES: Record<OrbitalTone, { border: string; text: string; glow: string; badgeBg: string }> = {
  cyan: { border: "border-jarvis-cyan/40", text: "text-jarvis-cyan", glow: "hover:shadow-glow-sm", badgeBg: "bg-jarvis-cyan" },
  blue: { border: "border-jarvis-blue/40", text: "text-jarvis-blue", glow: "hover:shadow-glow-sm", badgeBg: "bg-jarvis-blue" },
  violet: { border: "border-jarvis-violet/40", text: "text-jarvis-violet", glow: "", badgeBg: "bg-jarvis-violet" },
  amber: { border: "border-jarvis-amber/40", text: "text-jarvis-amber", glow: "", badgeBg: "bg-jarvis-amber" },
  emerald: { border: "border-jarvis-emerald/40", text: "text-jarvis-emerald", glow: "", badgeBg: "bg-jarvis-emerald" },
  rose: { border: "border-jarvis-rose/40", text: "text-jarvis-rose", glow: "", badgeBg: "bg-jarvis-rose" },
};

interface OrbitalNodeProps {
  x: number;
  y: number;
  icon: LucideIcon;
  label: string;
  sublabel?: string;
  tone?: OrbitalTone;
  badge?: number | string;
  active?: boolean;
  delay?: number;
  compact?: boolean;
  onClick: () => void;
}

/**
 * A single floating glass HUD widget positioned on an orbit ring. Pure
 * absolute positioning driven by the parent's trig — this component only
 * knows its own (x, y) center point, not the ring it belongs to.
 */
const OrbitalNode = forwardRef<HTMLButtonElement, OrbitalNodeProps>(function OrbitalNode(
  { x, y, icon: Icon, label, sublabel, tone = "cyan", badge, active, delay = 0, compact, onClick },
  ref
) {
  const t = TONE_STYLES[tone];

  return (
    <motion.button
      ref={ref}
      onClick={onClick}
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{
        opacity: 1,
        scale: 1,
        y: [0, -5, 0],
      }}
      transition={{
        opacity: { duration: 0.4, delay },
        scale: { duration: 0.4, delay },
        y: { duration: 4.5 + (delay % 1), repeat: Infinity, ease: "easeInOut", delay },
      }}
      whileHover={{ scale: 1.09, y: -2 }}
      whileTap={{ scale: 0.97 }}
      className={clsx(
        "hud-corner group absolute flex flex-col items-center justify-center gap-1 rounded-2xl border bg-jarvis-panel/60 px-3 py-2.5 text-center shadow-elevated backdrop-blur-2xl transition-colors duration-200",
        compact ? "w-[104px]" : "w-[128px]",
        active ? "border-jarvis-cyan bg-jarvis-cyan/10 shadow-glow-sm" : t.border,
        t.glow
      )}
      style={{ left: x, top: y, transform: "translate(-50%, -50%)" }}
    >
      {/* Top glass sheen — a child rather than ::before, since hud-corner
          already owns ::before/::after for the corner brackets. */}
      <span className="pointer-events-none absolute inset-x-0 top-0 h-1/2 rounded-t-2xl bg-gradient-to-b from-white/[0.06] to-transparent" />
      {badge !== undefined && badge !== 0 && badge !== "" && (
        <span
          className={clsx(
            "absolute -right-1.5 -top-1.5 flex h-5 min-w-[20px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white shadow-glow-sm",
            t.badgeBg
          )}
        >
          {badge}
        </span>
      )}
      <Icon className={clsx("h-4 w-4", t.text)} />
      <span className="truncate text-[11px] font-semibold uppercase tracking-wide text-jarvis-text">{label}</span>
      {sublabel && <span className="truncate text-[10px] text-jarvis-muted">{sublabel}</span>}
    </motion.button>
  );
});

export default OrbitalNode;
