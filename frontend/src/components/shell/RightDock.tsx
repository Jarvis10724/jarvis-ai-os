import { AnimatePresence, motion } from "framer-motion";
import { Bell, Bot, BrainCircuit, Clock, type LucideIcon } from "lucide-react";
import clsx from "clsx";

import { useDashboardUI, type DockPanel } from "@/context/DashboardUIContext";
import NotificationsCenter from "@/components/shell/panels/NotificationsCenter";
import TimelinePanel from "@/components/shell/panels/TimelinePanel";
import MemoryPanel from "@/components/shell/panels/MemoryPanel";
import AgentsPanel from "@/components/shell/panels/AgentsPanel";

const DOCK_ITEMS: { key: DockPanel; label: string; icon: LucideIcon }[] = [
  { key: "timeline", label: "Timeline", icon: Clock },
  { key: "memory", label: "AI Memory", icon: BrainCircuit },
  { key: "agents", label: "Active Agents", icon: Bot },
  { key: "notifications", label: "Notifications", icon: Bell },
];

/**
 * The persistent right dock of the AI OS shell. A thin activity-bar strip is
 * always visible (desktop); clicking an icon expands the selected panel into a
 * fixed-width column. Only one panel is open at a time. On mobile the strip is
 * hidden and the panel opens as a full-screen overlay (toggled from the left
 * rail / mobile nav). Every panel reads the active company/project from context
 * — the Shared Project System is the single source of truth.
 */
export default function RightDock() {
  const { activePanel, closePanel, togglePanel } = useDashboardUI();

  function renderPanel(panel: DockPanel) {
    switch (panel) {
      case "timeline":
        return <TimelinePanel onClose={closePanel} />;
      case "memory":
        return <MemoryPanel onClose={closePanel} />;
      case "agents":
        return <AgentsPanel onClose={closePanel} />;
      case "notifications":
        return <NotificationsCenter onClose={closePanel} />;
    }
  }

  return (
    <>
      {/* Mobile backdrop (only when a panel is open on small screens) */}
      <AnimatePresence>
        {activePanel && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closePanel}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Panel column: static (in flow) on lg, fixed overlay on mobile */}
      <AnimatePresence>
        {activePanel && (
          <motion.aside
            key={activePanel}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-y-0 right-0 z-40 w-full max-w-sm border-l border-jarvis-border/60 bg-jarvis-panel/80 backdrop-blur-2xl lg:static lg:z-auto lg:w-[360px] lg:max-w-none lg:shrink-0"
          >
            {renderPanel(activePanel)}
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Activity bar — always visible on desktop */}
      <nav className="hidden w-12 shrink-0 flex-col items-center gap-1 border-l border-jarvis-border/60 bg-jarvis-panel/50 py-4 backdrop-blur-2xl lg:flex">
        {DOCK_ITEMS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => togglePanel(key)}
            title={label}
            className={clsx(
              "press-scale flex h-10 w-10 items-center justify-center rounded-xl border transition-all duration-200",
              activePanel === key
                ? "border-jarvis-cyan/50 bg-jarvis-cyan/10 text-jarvis-cyan shadow-glow-sm"
                : "border-transparent text-jarvis-muted hover:border-jarvis-border hover:bg-jarvis-panel2/50 hover:text-jarvis-cyan"
            )}
          >
            <Icon className="h-5 w-5" />
          </button>
        ))}
      </nav>
    </>
  );
}
