import { createContext, useContext, type ReactNode } from "react";

// The panels the persistent right dock can show. One at a time.
export type DockPanel = "workspace" | "notifications" | "timeline" | "memory" | "agents";

// Small context so deeply nested dashboard widgets (e.g. the CEO
// dashboard's notifications snapshot card) and the shell chrome (left rail,
// mobile nav) can trigger shell-owned surfaces — the right dock panels, the
// quick-actions modal, the command palette — without threading callbacks
// through every page that renders <DashboardShell>.
interface DashboardUIContextValue {
  openQuickActions: () => void;
  openCommandPalette: () => void;
  // Right dock
  activePanel: DockPanel | null;
  openPanel: (panel: DockPanel) => void;
  closePanel: () => void;
  togglePanel: (panel: DockPanel) => void;
  // Back-compat alias — existing callers open the notifications surface, which
  // is now the notifications dock panel.
  openNotifications: () => void;
}

const DashboardUIContext = createContext<DashboardUIContextValue | undefined>(undefined);

export function DashboardUIProvider({
  value,
  children,
}: {
  value: DashboardUIContextValue;
  children: ReactNode;
}) {
  return <DashboardUIContext.Provider value={value}>{children}</DashboardUIContext.Provider>;
}

export function useDashboardUI() {
  const ctx = useContext(DashboardUIContext);
  if (!ctx) throw new Error("useDashboardUI must be used within DashboardShell");
  return ctx;
}
