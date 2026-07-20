import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import CommandPalette from "@/components/CommandPalette";
import MobileNav from "@/components/MobileNav";
import NotificationsPanel from "@/components/NotificationsPanel";
import QuickActions from "@/components/QuickActions";
import RadialNav from "@/components/RadialNav";
import TopNav from "@/components/TopNav";
import { DashboardUIProvider } from "@/context/DashboardUIContext";
import { useAutoDailyBriefing } from "@/hooks/useAutoDailyBriefing";
import { useGlobalHotkey } from "@/hooks/useGlobalHotkey";

// The persistent shell: mounted once by App.tsx's layout route, not
// per-page. Sidebar/TopNav/MobileNav/panels/the ambient background all live
// for the whole authenticated session — only <Outlet/> (the routed page
// content) swaps and transitions on navigation.
export default function DashboardShell() {
  const [notificationsOpen, setNotificationsOpen] = useState(false);
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
        openNotifications: () => setNotificationsOpen(true),
        openQuickActions: () => setQuickActionsOpen(true),
        openCommandPalette: () => setCommandPaletteOpen(true),
      }}
    >
      <div className="flex h-screen w-screen overflow-hidden bg-jarvis-bg bg-grid-pattern bg-grid">
        {/* Decorative ambient glow layer — fixed behind every screen so the
            whole app shares one quietly "alive" backdrop, not just Chat. */}
        <div className="ambient-orbs" aria-hidden="true">
          <span
            className="h-[26rem] w-[26rem] bg-jarvis-cyan"
            style={{ top: "-8rem", left: "-6rem", animationDelay: "0s" }}
          />
          <span
            className="h-[22rem] w-[22rem] bg-jarvis-violet"
            style={{ top: "40%", right: "-8rem", animationDelay: "3s" }}
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
            onToggleNotifications={() => setNotificationsOpen((v) => !v)}
            onToggleQuickActions={() => setQuickActionsOpen((v) => !v)}
            onOpenMobileNav={() => setMobileNavOpen(true)}
            unreadNotifications={3}
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

        <NotificationsPanel open={notificationsOpen} onClose={() => setNotificationsOpen(false)} />
        <QuickActions open={quickActionsOpen} onClose={() => setQuickActionsOpen(false)} />
        <CommandPalette open={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} />
      </div>
    </DashboardUIProvider>
  );
}
