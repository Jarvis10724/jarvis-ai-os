import { useEffect, useRef } from "react";

import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { generateDailyBriefingContent } from "@/lib/dailyBriefing";

const STALE_MS = 60 * 60 * 1000; // 1 hour — matches the "auto-refresh if stale" spec.

// Guards against re-checking on every route change within the same app
// session (DashboardShell — and therefore this hook — remounts on every
// SPA navigation). A fresh check only makes sense once per cooldown window;
// resets naturally on a full page reload, which is exactly "opening Jarvis."
const CHECK_COOLDOWN_MS = 5 * 60 * 1000;
let lastCheckedAt = 0;
let checkInFlight = false;

/**
 * Ensures the Daily Briefing is fresh whenever Jarvis is opened, without
 * waiting on the 7:09 AM scheduled job:
 *   - If no briefing exists yet today (or ever), generates one immediately.
 *   - If the latest briefing is older than an hour, regenerates it.
 *   - Otherwise does nothing — the scheduled job or a recent open already
 *     covered it.
 * Runs silently in the background (errors are swallowed) so it never blocks
 * or interrupts whatever page the user actually opened. The Daily Brief
 * page's manual "Regenerate" button remains the explicit fallback.
 */
export function useAutoDailyBriefing() {
  const { companies, loading } = useCompany();
  const companiesRef = useRef(companies);
  companiesRef.current = companies;

  useEffect(() => {
    if (loading) return; // wait until we know the real company list
    const now = Date.now();
    if (checkInFlight || now - lastCheckedAt < CHECK_COOLDOWN_MS) return;

    checkInFlight = true;
    lastCheckedAt = now;
    let cancelled = false;

    (async () => {
      try {
        const latest = await api.getLatestDailyBriefing().catch(() => null);
        const ageMs = latest?.generated_at ? now - new Date(latest.generated_at).getTime() : Infinity;
        if (ageMs <= STALE_MS) return; // fresh enough, nothing to do
        if (cancelled) return;

        const content = await generateDailyBriefingContent(companiesRef.current);
        if (cancelled) return;
        await api.saveDailyBriefing(content);
      } catch {
        // Best-effort background refresh — silent failure is correct here.
      } finally {
        checkInFlight = false;
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loading]);
}
