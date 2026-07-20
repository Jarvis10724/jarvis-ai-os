import { CalendarDays } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill, { type StatusTone } from "@/components/StatusPill";
import { CHANNEL_LABELS, MOCK_CONTENT } from "@/mock/contentCalendar";
import type { ContentCalendarItem } from "@/types";

const STATUS_TONE: Record<ContentCalendarItem["status"], StatusTone> = {
  idea: "neutral",
  drafting: "info",
  scheduled: "progress",
  published: "success",
};

export default function ContentCalendarPage() {
  const sorted = [...MOCK_CONTENT].sort((a, b) => a.date.localeCompare(b.date));

  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={CalendarDays}
            title="Content Calendar"
            description={`Upcoming content across every channel for ${company.name}.`}
          />

          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto p-4">
            <div className="space-y-2">
              {sorted.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-4 rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-3"
                >
                  <div className="w-20 shrink-0 text-center">
                    <p className="font-display text-sm font-bold text-jarvis-cyan">
                      {new Date(item.date + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    </p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-jarvis-text">{item.title}</p>
                    <p className="text-xs text-jarvis-muted">{CHANNEL_LABELS[item.channel]}</p>
                  </div>
                  <StatusPill label={item.status} tone={STATUS_TONE[item.status]} />
                </div>
              ))}
              {sorted.length === 0 && (
                <p className="py-16 text-center text-sm text-jarvis-muted">Nothing scheduled yet.</p>
              )}
            </div>
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
