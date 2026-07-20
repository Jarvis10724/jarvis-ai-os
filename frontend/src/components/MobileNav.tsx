import { AnimatePresence, motion } from "framer-motion";
import { Bell, Bot, BrainCircuit, Clock, X, type LucideIcon } from "lucide-react";

import CompanySwitcher from "@/components/CompanySwitcher";
import ProjectSwitcher from "@/components/ProjectSwitcher";
import { SidebarBrand, SidebarNav, SystemLoadCard } from "@/components/Sidebar";
import { useDashboardUI, type DockPanel } from "@/context/DashboardUIContext";

const PANELS: { key: DockPanel; label: string; icon: LucideIcon }[] = [
  { key: "timeline", label: "Timeline", icon: Clock },
  { key: "memory", label: "Memory", icon: BrainCircuit },
  { key: "agents", label: "Agents", icon: Bot },
  { key: "notifications", label: "Alerts", icon: Bell },
];

export default function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { openPanel } = useDashboardUI();
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "tween", duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-y-0 left-0 z-50 flex w-80 max-w-[85vw] flex-col border-r border-jarvis-border/60 bg-jarvis-panel/95 backdrop-blur-2xl md:hidden"
          >
            <div className="flex items-center justify-between border-b border-jarvis-border/60 pr-3">
              <SidebarBrand />
              <button
                onClick={onClose}
                className="rounded-lg p-2 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <CompanySwitcher />
            <ProjectSwitcher />
            {/* Right-dock panels (Timeline / Memory / Agents / Notifications) */}
            <div className="mx-3 mt-2 grid grid-cols-4 gap-1.5">
              {PANELS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => {
                    openPanel(key);
                    onClose();
                  }}
                  className="flex flex-col items-center gap-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/30 py-2 text-[10px] text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
            <SidebarNav onNavigate={onClose} />
            <SystemLoadCard />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
