import type { Company } from "@/types";

/**
 * Per-workspace theming — every company gets its own accent + monogram so it
 * feels like its own operating environment, while the shell stays identical.
 * Derived deterministically on the frontend from the company id/name, so there
 * is NO backend field, migration, or API change (companies already carry id +
 * name). Consumers read CSS vars (--ws-accent, --ws-accent-soft, --ws-glow)
 * so the accent propagates app-wide without per-component edits.
 */

export interface WorkspaceTheme {
  /** Base hue (deg) — the workspace's signature color. */
  hue: number;
  /** Solid accent, e.g. for text/icons/borders. */
  accent: string;
  /** Translucent accent for rings/fills. */
  accentSoft: string;
  /** Very faint accent for subtle tinted backgrounds (chips, hovers). */
  accentFaint: string;
  /** Glow color for blooms/shadows. */
  glow: string;
  /** Two-layer ambient gradient for the shell backdrop. */
  gradient: string;
  /** 1–2 letter monogram "logo". */
  monogram: string;
}

// Curated, on-brand accent hues (cyan → teal → blue → indigo → violet →
// magenta → gold). A designed palette reads more premium than random hues and
// stays legible on the dark shell. Jarvis's default (no active company) is cyan.
const ACCENT_HUES = [189, 168, 210, 234, 266, 292, 322, 45];
const JARVIS_HUE = 189;

function hashString(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function monogramFor(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "JV";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function themeForCompany(company: Company | null | undefined): WorkspaceTheme {
  const hue = company ? ACCENT_HUES[hashString(company.id || company.name) % ACCENT_HUES.length] : JARVIS_HUE;
  const accent = `hsl(${hue} 88% 62%)`;
  const accentSoft = `hsla(${hue}, 88%, 62%, 0.5)`;
  const accentFaint = `hsla(${hue}, 88%, 62%, 0.14)`;
  const glow = `hsla(${hue}, 92%, 60%, 0.38)`;
  const gradient =
    `radial-gradient(ellipse 80% 50% at 18% -12%, hsla(${hue}, 85%, 55%, 0.20), transparent 60%), ` +
    `radial-gradient(ellipse 60% 40% at 92% 8%, hsla(${(hue + 46) % 360}, 80%, 55%, 0.12), transparent 55%)`;
  return {
    hue,
    accent,
    accentSoft,
    accentFaint,
    glow,
    gradient,
    monogram: company ? monogramFor(company.name) : "JV",
  };
}
