import type { ReactNode } from "react";
import { motion } from "framer-motion";

import SampleDataBadge from "@/components/SampleDataBadge";

interface ModulePageHeaderProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  /** Set false for modules that aren't backed by mock data (rare). */
  sampleData?: boolean;
  actions?: ReactNode;
}

/**
 * Consistent header for every OS module page: icon, title, one-line
 * description, a "Sample Data" flag when relevant, and a slot for
 * page-specific actions (buttons, filters). Keeping this shared means
 * every module reads the same way even before any of them have live data.
 */
export default function ModulePageHeader({
  icon: Icon,
  title,
  description,
  sampleData = true,
  actions,
}: ModulePageHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="hud-panel hud-corner flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 shadow-glow-sm">
          <Icon className="h-6 w-6 text-jarvis-cyan" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-lg font-bold tracking-widest text-jarvis-text text-glow">
              {title.toUpperCase()}
            </h1>
            {sampleData && <SampleDataBadge />}
          </div>
          <p className="text-sm text-jarvis-muted">{description}</p>
        </div>
      </div>

      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </motion.div>
  );
}
