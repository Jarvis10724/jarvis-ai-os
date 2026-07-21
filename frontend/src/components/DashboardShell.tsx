import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import CommandPalette from "@/components/CommandPalette";
import MobileNav from "@/components/MobileNav";
import QuickActions from "@/components/QuickActions";
import RadialNav from "@/components/RadialNav";
import RightDock from "@/components/shell/RightDock";
import WorkspaceThemeVars from "@/components/shell/WorkspaceThemeVars";
import TopNav from "@/components/TopNav";
import { DashboardUIProvider, type DockPanel } from "@/context/DashboardUIContext";
import { useAutoDailyBriefing } from "@/hooks/useAutoDailyBriefing";
import { useGlobalHotkey } from "@/hooks/useGlobalHotkey";

// The persistent shell: mounted once by App.tsx's layout route, not
// per-page. Sidebar/TopNav/MobileNav/panels/the ambient background all live
// for the whole authenticated session — only <Outlet/> (the routed page
// content) swaps and transitions on navigation.
export default function DashboardShell() {
  const [activePanel, setActivePanel] = useState<DockPanel | null>(null);
  const [quickActionsOpen, setQuickActionsOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const location = useLocation();

  // Shell mounts once now, so this fires once per real app-open rather than
  // once per navigation — still safe even if that changes later, since the
  // hook has its own module-level cooldown guard (see useAutoDailyBriefing.ts).
  useAutoDailyBriefing();

  // Cmd/Ctrl+K anywhere in the app — only clean to register once now that
  // the shell is persistent instead of remounting per page.
  useGlobalHotkey("k", (e) => {
    e.preventDefault();
    setCommandPaletteOpen(true);
  });

  return (
    <DashboardUIProvider
      value={{
        activePanel,
        openPanel: (panel) => setActivePanel(panel),
        closePanel: () => setActivePanel(null),
        togglePanel: (panel) => setActivePanel((cur) => (cur === panel ? null : panel)),
        openNotifications: () => setActivePanel("notifications"),
        openQuickActions: () => setQuickActionsOpen(true),
        openCommandPalette: () => setCommandPaletteOpen(true),
      }}
    >
      <div className="flex h-screen w-screen overflow-hidden bg-jarvis-bg bg-grid-pattern bg-grid">
        {/* Applies the active workspace's accent theme (CSS vars) app-wide. */}
        <WorkspaceThemeVars />
        {/* Decorative ambient glow layer — fixed behind every screen so the
            whole app shares one quietly "alive" backdrop, not just Chat. */}
        <div className="ambient-orbs" aria-hidden="true">
          {/* The two lead orbs carry the active workspace's accent (cross-fading
              on switch) so the whole backdrop "changes universe"; the third
              stays neutral blue for depth variety. */}
          <span
            className="h-[26rem] w-[26rem]"
            style={{ top: "-8rem", left: "-6rem", animationDelay: "0s", backgroundColor: "var(--ws-accent)" }}
          />
          <span
            className="h-[22rem] w-[22rem]"
            style={{ top: "40%", right: "-8rem", animationDelay: "3s", backgroundColor: "var(--ws-glow)" }}
          />
          <span
            className="h-[20rem] w-[20rem] bg-jarvis-blue"
            style={{ bottom: "-6rem", left: "30%", animationDelay: "6s" }}
          />
        </div>
        <RadialNav />
        <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

        <div className="flex min-w-0 flex-1 flex-col">
          <TopNav
            onToggleNotifications={() => setActivePanel((cur) => (cur === "notifications" ? null : "notifications"))}
            onToggleQuickActions={() => setQuickActionsOpen((v) => !v)}
            onOpenMobileNav={() => setMobileNavOpen(true)}
            unreadNotifications={0}
          />
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
              className="flex min-h-0 flex-1 flex-col"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>

        <RightDock />

        <QuickActions open={quickActionsOpen} onClose={() => setQuickActionsOpen(false)} />
        <CommandPalette open={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} />
      </div>
    </DashboardUIProvider>
  );
}
