import { createContext, useContext, type ReactNode } from "react";

// Small context so deeply nested dashboard widgets (e.g. the CEO
// dashboard's notifications snapshot card) can trigger chrome owned by
// DashboardShell — like opening the notifications slide-over — without
// threading callbacks through every page that renders <DashboardShell>.
interface DashboardUIContextValue {
  openNotifications: () => void;
  openQuickActions: () => void;
  openCommandPalette: () => void;
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
