import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Loader2, PlugZap, RefreshCw } from "lucide-react";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import { api } from "@/api/client";
import { MOCK_PRODUCTION_RUNS } from "@/mock/manufacturing";
import { MOCK_PROJECTS } from "@/mock/projects";
import type { CalendarEventView } from "@/types";

const AUTO_REFRESH_MS = 60_000;

function isToday(iso: string | null): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

function formatTime(iso: string | null, allDay: boolean): string {
  if (!iso) return "";
  if (allDay) return "All day";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function formatDay(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

const upcomingDeadlines = MOCK_PROJECTS.filter((p) => p.status !== "done" && p.dueDate)
  .sort((a, b) => new Date(a.dueDate!).getTime() - new Date(b.dueDate!).getTime())
  .slice(0, 3);

const manufacturingMilestones = MOCK_PRODUCTION_RUNS.filter((r) => r.eta && r.stage !== "complete")
  .sort((a, b) => new Date(a.eta!).getTime() - new Date(b.eta!).getTime())
  .slice(0, 3);

/**
 * Today's meetings and the upcoming-events strip are both real (Phase 3b/3c
 * connected Calendar) and poll every 60s. Upcoming deadlines and
 * manufacturing milestones don't have a real backing table yet (Task has no
 * due-date column) — sample project due-dates and production-run ETAs,
 * both flagged.
 */
export default function CalendarCard({ companyId }: { companyId?: string } = {}) {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [todaysEvents, setTodaysEvents] = useState<CalendarEventView[]>([]);
  const [upcomingEvents, setUpcomingEvents] = useState<CalendarEventView[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const firstLoad = useRef(true);

  const load = useCallback(async () => {
    if (firstLoad.current) setLoading(true);
    else setRefreshing(true);
    try {
      const events = await api.listCalendarEvents({ companyId, maxResults: 30, upcomingOnly: true });
      setTodaysEvents(events.filter((e) => isToday(e.start)));
      setUpcomingEvents(events.filter((e) => !isToday(e.start)).slice(0, 5));
      setConnected(true);
    } catch {
      setConnected(false);
    } finally {
      firstLoad.current = false;
      setLoading(false);
      setRefreshing(false);
    }
  }, [companyId]);

  useEffect(() => {
    firstLoad.current = true;
    load();
    const interval = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-jarvis-cyan" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">CALENDAR</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-jarvis-muted">
            {new Date().toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
          </span>
          <button
            onClick={() => load()}
            disabled={loading || refreshing}
            title="Refresh now"
            className="press-scale rounded-lg p-1 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-cyan disabled:opacity-40"
          >
            <RefreshCw className={clsx("h-3.5 w-3.5", refreshing && "animate-spin")} />
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div>
          <p className="mb-1.5 text-[11px] uppercase tracking-wide text-jarvis-muted">Today's meetings</p>
          {loading ? (
            <div className="h-6 w-full animate-pulse rounded-lg bg-jarvis-panel2/50" />
          ) : connected === false ? (
            <div className="flex items-center gap-2 rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/30 px-2.5 py-2 text-xs text-jarvis-muted">
              <PlugZap className="h-3.5 w-3.5" />
              Calendar isn't connected —{" "}
              <Link to="/integrations" className="font-medium text-jarvis-cyan hover:underline">
                connect it
              </Link>
            </div>
          ) : todaysEvents.length === 0 ? (
            <p className="text-xs text-jarvis-muted">Nothing on the calendar today.</p>
          ) : (
            <ul className="space-y-1.5">
              {todaysEvents.map((e) => (
                <li
                  key={e.id}
                  className="flex items-center gap-3 rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2.5 py-1.5"
                >
                  <span className="h-2 w-2 shrink-0 rounded-full bg-jarvis-blue" />
                  <span className="min-w-0 flex-1 truncate text-sm text-jarvis-text">{e.summary || "(untitled)"}</span>
                  <span className="font-data shrink-0 text-xs text-jarvis-muted">{formatTime(e.start, e.all_day)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {connected && (
          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wide text-jarvis-muted">Upcoming</p>
            {upcomingEvents.length === 0 ? (
              <p className="text-xs text-jarvis-muted">Nothing else scheduled soon.</p>
            ) : (
              <ul className="space-y-1">
                {upcomingEvents.map((e) => (
                  <li key={e.id} className="flex items-center justify-between gap-2 truncate text-xs">
                    <span className="min-w-0 truncate text-jarvis-text">{e.summary || "(untitled)"}</span>
                    <span className="shrink-0 text-jarvis-muted">{formatDay(e.start)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div>
          <div className="mb-1.5 flex items-center gap-2">
            <p className="text-[11px] uppercase tracking-wide text-jarvis-muted">Upcoming deadlines</p>
            <SampleDataBadge />
          </div>
          <ul className="space-y-1">
            {upcomingDeadlines.map((p) => (
              <li key={p.id} className="truncate text-xs text-jarvis-muted">
                <span className="text-jarvis-text">{p.title}</span> — due {p.dueDate}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="mb-1.5 flex items-center gap-2">
            <p className="text-[11px] uppercase tracking-wide text-jarvis-muted">Manufacturing milestones</p>
            <SampleDataBadge />
          </div>
          <ul className="space-y-1">
            {manufacturingMilestones.map((r) => (
              <li key={r.id} className="truncate text-xs text-jarvis-muted">
                <span className="text-jarvis-text">{r.productName}</span> — ETA {r.eta}
              </li>
            ))}
          </ul>
        </div>

        {refreshing && (
          <p className="flex items-center gap-1 text-[10px] text-jarvis-faint">
            <Loader2 className="h-2.5 w-2.5 animate-spin" /> Refreshing…
          </p>
        )}
      </div>
    </div>
  );
}
