import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import type { NotificationItem } from "@/types";

export const NOTIFICATIONS: NotificationItem[] = [
  {
    id: "1",
    title: "Shopify order spike",
    description: "42 new orders in the last hour — 3x the daily average.",
    time: "5m ago",
    severity: "success",
    read: false,
  },
  {
    id: "2",
    title: "QuickBooks sync warning",
    description: "2 invoices failed to sync — check the integrations tab.",
    time: "1h ago",
    severity: "warning",
    read: false,
  },
  {
    id: "3",
    title: "Automation failed",
    description: "Weekly social post automation hit an API rate limit.",
    time: "3h ago",
    severity: "critical",
    read: false,
  },
  {
    id: "4",
    title: "Research complete",
    description: "Competitor pricing research is ready to review.",
    time: "Yesterday",
    severity: "info",
    read: true,
  },
];

export const SEVERITY_ICON: Record<NotificationItem["severity"], typeof Info> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  critical: XCircle,
};

export const SEVERITY_STYLES: Record<NotificationItem["severity"], string> = {
  info: "text-jarvis-blue border-jarvis-blue/40 bg-jarvis-blue/10",
  success: "text-jarvis-emerald border-jarvis-emerald/40 bg-jarvis-emerald/10",
  warning: "text-jarvis-amber border-jarvis-amber/40 bg-jarvis-amber/10",
  critical: "text-jarvis-rose border-jarvis-rose/40 bg-jarvis-rose/10",
};

interface NotificationsPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function NotificationsPanel({ open, onClose }: NotificationsPanelProps) {
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
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="hud-panel fixed right-0 top-0 z-50 h-full w-full max-w-sm rounded-none border-l border-jarvis-border/60"
          >
            <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
              <div className="flex items-center gap-2">
                <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                  NOTIFICATIONS
                </h2>
                <SampleDataBadge />
              </div>
              <button
                onClick={onClose}
                className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <ul className="space-y-3 overflow-y-auto p-5">
              {NOTIFICATIONS.map((n, i) => {
                const Icon = SEVERITY_ICON[n.severity];
                return (
                  <motion.li
                    key={n.id}
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.06 * i, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                    className={clsx(
                      "rounded-xl border p-3 transition-colors duration-150",
                      n.read
                        ? "border-jarvis-border/40 bg-jarvis-panel2/25"
                        : "border-jarvis-border/70 bg-jarvis-panel2/50"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className={clsx(
                          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                          SEVERITY_STYLES[n.severity]
                        )}
                      >
                        <Icon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-jarvis-text">{n.title}</p>
                        <p className="mt-0.5 text-xs leading-relaxed text-jarvis-muted">{n.description}</p>
                        <p className="mt-1 text-[10px] uppercase tracking-wide text-jarvis-faint">
                          {n.time}
                        </p>
                      </div>
                      {!n.read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-jarvis-cyan shadow-glow-sm" />}
                    </div>
                  </motion.li>
                );
              })}
            </ul>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
