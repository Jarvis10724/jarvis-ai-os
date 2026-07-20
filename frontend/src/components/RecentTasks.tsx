import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import type { TaskItem, TaskStatus } from "@/types";

const MOCK_TASKS: TaskItem[] = [
  { id: "1", title: "Design new logo concepts", status: "in_progress", plugin_name: "logo_design" },
  { id: "2", title: "Draft Q3 marketing site copy", status: "todo", plugin_name: "web_builder" },
  { id: "3", title: "Sync QuickBooks invoices", status: "done", plugin_name: "quickbooks" },
  { id: "4", title: "Research competitor pricing", status: "in_progress", plugin_name: "deep_research" },
  { id: "5", title: "Automate weekly Shopify report", status: "failed", plugin_name: "automation" },
];

const STATUS_META: Record<TaskStatus, { icon: typeof CheckCircle2; className: string; label: string }> = {
  todo: { icon: CircleDashed, className: "text-jarvis-muted", label: "Queued" },
  in_progress: { icon: Loader2, className: "text-jarvis-amber animate-spin", label: "Running" },
  done: { icon: CheckCircle2, className: "text-jarvis-emerald", label: "Done" },
  failed: { icon: XCircle, className: "text-jarvis-rose", label: "Failed" },
};

export default function RecentTasks({ tasks = MOCK_TASKS }: { tasks?: TaskItem[] }) {
  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
          RECENT TASKS
        </h2>
        <div className="flex items-center gap-2">
          <SampleDataBadge />
          <span className="text-xs text-jarvis-muted">{tasks.length} active</span>
        </div>
      </div>

      <ul className="flex-1 divide-y divide-jarvis-border/40 overflow-y-auto">
        {tasks.map((task, i) => {
          const meta = STATUS_META[task.status];
          const Icon = meta.icon;
          return (
            <motion.li
              key={task.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 * i, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="flex items-center gap-3 px-5 py-3 transition-colors duration-150 hover:bg-jarvis-panel2/30"
            >
              <Icon className={clsx("h-4 w-4 shrink-0", meta.className)} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-jarvis-text">{task.title}</p>
                {task.plugin_name && (
                  <p className="font-data text-[11px] text-jarvis-muted">{task.plugin_name}</p>
                )}
              </div>
              <span className="shrink-0 text-xs text-jarvis-muted">{meta.label}</span>
            </motion.li>
          );
        })}
      </ul>
    </div>
  );
}
