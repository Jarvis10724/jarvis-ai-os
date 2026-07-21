import { useEffect } from "react";

import { useCompany } from "@/context/CompanyContext";
import { themeForCompany } from "@/lib/workspaceTheme";

/**
 * Applies the active workspace's theme as CSS custom properties on <html>, so
 * every surface that reads var(--ws-accent) / --ws-accent-soft / --ws-glow /
 * --ws-gradient repaints when you switch companies — "switching universes"
 * without touching the shell. Renders nothing.
 */
export default function WorkspaceThemeVars() {
  const { activeCompany } = useCompany();

  useEffect(() => {
    const theme = themeForCompany(activeCompany);
    const root = document.documentElement;
    root.style.setProperty("--ws-accent", theme.accent);
    root.style.setProperty("--ws-accent-soft", theme.accentSoft);
    root.style.setProperty("--ws-glow", theme.glow);
    root.style.setProperty("--ws-gradient", theme.gradient);
    root.style.setProperty("--ws-hue", String(theme.hue));
  }, [activeCompany]);

  return null;
}
