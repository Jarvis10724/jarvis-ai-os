import clsx from "clsx";

const TONE_STYLES = {
  neutral: "border-jarvis-muted/40 bg-jarvis-muted/10 text-jarvis-muted",
  info: "border-jarvis-blue/40 bg-jarvis-blue/10 text-jarvis-blue",
  progress: "border-jarvis-amber/40 bg-jarvis-amber/10 text-jarvis-amber",
  success: "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald",
  danger: "border-jarvis-rose/40 bg-jarvis-rose/10 text-jarvis-rose",
  accent: "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan",
} as const;

export type StatusTone = keyof typeof TONE_STYLES;

/** Small pill badge used across every module for status/stage labels. */
export default function StatusPill({ label, tone = "neutral" }: { label: string; tone?: StatusTone }) {
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        TONE_STYLES[tone]
      )}
    >
      {label}
    </span>
  );
}
