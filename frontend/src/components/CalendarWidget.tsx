import { CalendarClock } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import type { CalendarEvent } from "@/types";

const EVENTS: CalendarEvent[] = [
  { id: "1", title: "Supplier call — packaging", time: "9:30 AM", type: "meeting" },
  { id: "2", title: "Shopify inventory sync", time: "12:00 PM", type: "reminder" },
  { id: "3", title: "Investor update due", time: "5:00 PM", type: "deadline" },
];

const TYPE_STYLES: Record<CalendarEvent["type"], string> = {
  meeting: "bg-jarvis-blue",
  deadline: "bg-jarvis-rose",
  reminder: "bg-jarvis-amber",
};

function buildWeekDays(): { label: string; date: number; isToday: boolean }[] {
  const today = new Date();
  const days: { label: string; date: number; isToday: boolean }[] = [];
  for (let offset = -3; offset <= 3; offset++) {
    const d = new Date(today);
    d.setDate(today.getDate() + offset);
    days.push({
      label: d.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2),
      date: d.getDate(),
      isToday: offset === 0,
    });
  }
  return days;
}

export default function CalendarWidget() {
  const days = buildWeekDays();

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-jarvis-cyan" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            CALENDAR
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <SampleDataBadge />
          <span className="text-xs text-jarvis-muted">
            {new Date().toLocaleDateString(undefined, { month: "short", year: "numeric" })}
          </span>
        </div>
      </div>

      <div className="flex justify-between px-5 py-4">
        {days.map((day, i) => (
          <motion.div
            key={`${day.label}-${day.date}`}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.03 * i, duration: 0.25 }}
            className={clsx(
              "flex w-9 flex-col items-center gap-1 rounded-lg py-1.5 text-xs transition-colors duration-200",
              day.isToday
                ? "border border-jarvis-cyan/50 bg-jarvis-cyan/10 text-jarvis-cyan shadow-glow-sm"
                : "text-jarvis-muted"
            )}
          >
            <span>{day.label}</span>
            <span className="font-data font-semibold">{day.date}</span>
          </motion.div>
        ))}
      </div>

      <ul className="flex-1 space-y-2 overflow-y-auto px-5 pb-5">
        {EVENTS.map((event, i) => (
          <motion.li
            key={event.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + 0.05 * i, duration: 0.3 }}
            className="flex items-center gap-3 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2.5 transition-colors duration-150 hover:border-jarvis-border-soft"
          >
            <span className={clsx("h-2 w-2 shrink-0 rounded-full", TYPE_STYLES[event.type])} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-jarvis-text">{event.title}</p>
            </div>
            <span className="font-data shrink-0 text-xs text-jarvis-muted">{event.time}</span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
