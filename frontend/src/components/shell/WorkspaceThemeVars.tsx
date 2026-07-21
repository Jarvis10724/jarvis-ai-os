import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useCompany } from "@/context/CompanyContext";
import { themeForCompany } from "@/lib/workspaceTheme";

/**
 * Applies the active workspace's theme as CSS custom properties on <html>, so
 * every surface that reads var(--ws-accent) / --ws-accent-soft / --ws-glow /
 * --ws-gradient repaints when you switch companies. The accent vars are
 * registered as animatable <color>s (see index.css @property), so the change
 * cross-fades rather than snapping.
 *
 * On an actual workspace *switch* (not first mount) it also plays a one-shot
 * accent bloom over the screen — the "switching universes" moment — in the new
 * workspace's color. Purely decorative, pointer-events-none, reduced-motion
 * aware.
 */
export default function WorkspaceThemeVars() {
  const { activeCompany } = useCompany();
  const [flashKey, setFlashKey] = useState(0);
  const prevId = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    const theme = themeForCompany(activeCompany);
    const root = document.documentElement;
    root.style.setProperty("--ws-accent", theme.accent);
    root.style.setProperty("--ws-accent-soft", theme.accentSoft);
    root.style.setProperty("--ws-accent-faint", theme.accentFaint);
    root.style.setProperty("--ws-glow", theme.glow);
    root.style.setProperty("--ws-gradient", theme.gradient);
    root.style.setProperty("--ws-hue", String(theme.hue));
  }, [activeCompany]);

  // Trigger the bloom only on a real change of active workspace, never on the
  // initial mount (prevId starts undefined).
  useEffect(() => {
    const id = activeCompany?.id ?? null;
    if (prevId.current !== undefined && prevId.current !== id) {
      const reduce =
        typeof window !== "undefined" &&
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      if (!reduce) setFlashKey((k) => k + 1);
    }
    prevId.current = id;
  }, [activeCompany?.id]);

  if (flashKey === 0) return null;
  return (
    <motion.div
      key={flashKey}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-30"
      initial={{ opacity: 0 }}
      animate={{ opacity: [0, 0.55, 0] }}
      transition={{ duration: 0.9, ease: "easeOut", times: [0, 0.35, 1] }}
      style={{ background: "radial-gradient(circle at 50% 42%, var(--ws-glow), transparent 62%)" }}
    />
  );
}
