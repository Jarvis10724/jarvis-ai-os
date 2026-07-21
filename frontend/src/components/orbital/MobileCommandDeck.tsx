import { motion } from "framer-motion";
import clsx from "clsx";

import type { JarvisCoreState } from "@/components/JarvisCore";
import OrbitalCore from "@/components/orbital/OrbitalCore";
import { TONE_STYLES, type OrbitalTone } from "@/components/orbital/OrbitalNode";
import type { NodeSpec } from "@/components/orbital/types";

/**
 * The mobile Home — a thumb-first "command deck" instead of the desktop's
 * full-circle constellation (which clips on a phone). Layout, top → bottom:
 *
 *   1. AI Core hero (~40% of the viewport) — the breathing centerpiece and the
 *      push-to-talk button, carrying the active workspace's identity + accent.
 *   2. A curved thumb dock — the primary system actions on a shallow arc just
 *      under the Core, in easy one-thumb reach.
 *   3. A scrollable module grid — the workspace's modules as glass tiles, 3-up,
 *      never clipping, safe-area aware, with room at the bottom for the fixed
 *      VoiceConsole.
 *
 * Pure flex/grid (no absolute constellation math), so nothing overlaps or
 * clips at any phone width. Everything is driven by the same NodeSpec[] the
 * desktop layout uses, so the two never drift apart.
 */
export default function MobileCommandDeck({
  coreDiameter,
  coreState,
  coreTitle,
  coreSubtitle,
  hint,
  level,
  onCoreClick,
  dockSpecs,
  gridSpecs,
}: {
  coreDiameter: number;
  coreState: JarvisCoreState;
  coreTitle: string;
  coreSubtitle: string;
  hint?: string;
  level: number;
  onCoreClick: () => void;
  dockSpecs: NodeSpec[];
  gridSpecs: NodeSpec[];
}) {
  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* 1. Core hero */}
      <div
        className="relative flex shrink-0 items-center justify-center"
        style={{ height: "clamp(224px, 42vh, 380px)" }}
      >
        <div className="starfield absolute inset-0" aria-hidden="true" />
        <OrbitalCore
          diameter={coreDiameter}
          state={coreState}
          title={coreTitle}
          subtitle={coreSubtitle}
          hint={hint}
          level={level}
          onClick={onCoreClick}
        />
      </div>

      {/* 2. Curved thumb dock — primary system actions */}
      {dockSpecs.length > 0 && <CurvedDock specs={dockSpecs} />}

      {/* 3. Scrollable module grid */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-3 pb-28">
        <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-jarvis-faint">
          Workspace modules
        </p>
        <div className="grid grid-cols-3 gap-2.5">
          {gridSpecs.map((spec, i) => (
            <CommandTile key={spec.key} spec={spec} delay={i * 0.03} />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * A centered row of nodes laid on a shallow downward arc (a "cradle" under the
 * Core). The curve is a per-item translateY — layout stays flex, so it can
 * never push a node off-screen the way an absolute orbit can.
 */
function CurvedDock({ specs }: { specs: NodeSpec[] }) {
  const n = specs.length;
  const center = (n - 1) / 2;
  const amplitude = 14; // px of bow at the middle

  return (
    <div className="shrink-0 px-3 pb-1 pt-1">
      <div className="flex flex-wrap items-start justify-center gap-2">
        {specs.map((spec, i) => {
          const d = center === 0 ? 0 : (i - center) / center; // -1..1
          const dy = amplitude * (1 - d * d); // middle bows down most
          return <DockButton key={spec.key} spec={spec} offsetY={dy} delay={i * 0.05} />;
        })}
      </div>
    </div>
  );
}

function DockButton({ spec, offsetY, delay }: { spec: NodeSpec; offsetY: number; delay: number }) {
  const tone: OrbitalTone = spec.tone ?? "cyan";
  const t = TONE_STYLES[tone];
  const Icon = spec.icon;
  return (
    <motion.button
      onClick={spec.onClick}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: offsetY }}
      transition={{ duration: 0.35, delay, ease: [0.16, 1, 0.3, 1] }}
      whileTap={{ scale: 0.94 }}
      className={clsx(
        "relative flex min-h-[64px] w-[92px] flex-col items-center justify-center gap-1 rounded-2xl border bg-jarvis-panel/70 px-1 py-2 text-center shadow-elevated backdrop-blur-2xl transition-colors duration-200",
        spec.active ? "border-jarvis-cyan bg-jarvis-cyan/10 shadow-glow-sm" : t.border
      )}
    >
      {spec.badge !== undefined && spec.badge !== 0 && spec.badge !== "" && (
        <span
          className={clsx(
            "absolute -right-1.5 -top-1.5 flex h-5 min-w-[20px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white shadow-glow-sm",
            t.badgeBg
          )}
        >
          {spec.badge}
        </span>
      )}
      <Icon className={clsx("h-5 w-5 shrink-0", t.text)} />
      <span className="w-full text-[10px] font-semibold uppercase leading-tight tracking-wide text-jarvis-text">
        {spec.label}
      </span>
    </motion.button>
  );
}

function CommandTile({ spec, delay }: { spec: NodeSpec; delay: number }) {
  const tone: OrbitalTone = spec.tone ?? "cyan";
  const t = TONE_STYLES[tone];
  const Icon = spec.icon;
  return (
    <motion.button
      onClick={spec.onClick}
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, delay, ease: [0.16, 1, 0.3, 1] }}
      whileTap={{ scale: 0.96 }}
      className={clsx(
        "hud-corner relative flex min-h-[86px] flex-col items-center justify-center gap-1.5 rounded-2xl border bg-jarvis-panel/60 px-2 py-3 text-center shadow-elevated backdrop-blur-2xl transition-colors duration-200",
        spec.active ? "border-jarvis-cyan bg-jarvis-cyan/10 shadow-glow-sm" : t.border
      )}
    >
      <span className="pointer-events-none absolute inset-x-0 top-0 h-1/2 rounded-t-2xl bg-gradient-to-b from-white/[0.06] to-transparent" />
      {spec.badge !== undefined && spec.badge !== 0 && spec.badge !== "" && (
        <span
          className={clsx(
            "absolute -right-1.5 -top-1.5 flex h-5 min-w-[20px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white shadow-glow-sm",
            t.badgeBg
          )}
        >
          {spec.badge}
        </span>
      )}
      <Icon className={clsx("h-5 w-5", t.text)} />
      <span className="w-full truncate text-[11px] font-semibold text-jarvis-text">{spec.label}</span>
      {spec.sublabel && (
        <span className="w-full truncate text-[9px] leading-tight text-jarvis-muted">{spec.sublabel}</span>
      )}
    </motion.button>
  );
}
