import { AnimatePresence, motion } from "framer-motion";
import { Blocks, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { QUICK_ACTIONS, type QuickAction } from "@/lib/quickActions";

interface QuickActionsProps {
  open: boolean;
  onClose: () => void;
}

export default function QuickActions({ open, onClose }: QuickActionsProps) {
  const navigate = useNavigate();

  // Each Quick Action now opens its own persistent, streaming workspace
  // (Studio) rather than firing a one-shot plugin run.
  function handleRun(action: QuickAction) {
    onClose();
    navigate(`/studio/${action.pluginName}`);
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="hud-panel hud-corner fixed left-1/2 top-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 p-6 shadow-elevated-lg"
          >
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Blocks className="h-4 w-4 text-jarvis-cyan" />
                <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                  QUICK ACTIONS
                </h2>
              </div>
              <button
                onClick={onClose}
                className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
              {QUICK_ACTIONS.map((action, i) => (
                <motion.button
                  key={action.key}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.04 * i, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                  onClick={() => handleRun(action)}
                  className="press-scale group flex flex-col items-start gap-2 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 p-4 text-left transition-all duration-200 hover:border-jarvis-cyan/50 hover:bg-jarvis-cyan/10 hover:shadow-glow-sm"
                >
                  <action.icon className="h-5 w-5 text-jarvis-cyan transition-transform duration-200 group-hover:scale-110" />
                  <span className="text-sm font-medium text-jarvis-text">{action.label}</span>
                  <span className="text-xs text-jarvis-muted">{action.description}</span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
