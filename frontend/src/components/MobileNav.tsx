import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

import CompanySwitcher from "@/components/CompanySwitcher";
import { SidebarBrand, SidebarNav, SystemLoadCard } from "@/components/Sidebar";

export default function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
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
            <SidebarNav onNavigate={onClose} />
            <SystemLoadCard />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
