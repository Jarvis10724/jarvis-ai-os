import { useCallback, useEffect, useState } from "react";
import { Clock } from "lucide-react";

import { api, ApiError } from "@/api/client";
import { useProject } from "@/context/ProjectContext";
import PanelFrame, { PanelEmpty, PanelLoading } from "@/components/shell/panels/PanelFrame";
import type { ProjectEvent } from "@/types";

function ago(iso: string | null): string {
  if (!iso) return "";
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}

// Timeline of the ACTIVE project — the Shared Project System's Timeline bucket,
// live in the shell. Re-scopes whenever the active project changes.
export default function TimelinePanel({ onClose }: { onClose: () => void }) {
  const { activeProject, activeProjectId } = useProject();
  const [events, setEvents] = useState<ProjectEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!activeProjectId) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setEvents(await api.getProjectTimeline(activeProjectId, 100));
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [activeProjectId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PanelFrame
      title="Timeline"
      icon={Clock}
      onClose={onClose}
      onRefresh={load}
      refreshing={loading}
      subtitle={activeProject?.name ?? "No active project"}
    >
      {loading ? (
        <PanelLoading />
      ) : !activeProjectId ? (
        <PanelEmpty label="Select a project to see its timeline." />
      ) : events.length === 0 ? (
        <PanelEmpty label="No activity yet." />
      ) : (
        <ol className="space-y-2">
          {events.map((e) => (
            <li
              key={e.id}
              className="rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 px-3 py-2.5"
            >
              <div className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-jarvis-cyan shadow-glow-sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-jarvis-text">{e.title}</p>
                  {e.detail && <p className="mt-0.5 text-xs text-jarvis-muted">{e.detail}</p>}
                  <p className="mt-1 text-[10px] uppercase tracking-wide text-jarvis-faint">
                    {e.kind.replace(/_/g, " ")} · {ago(e.created_at)}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </PanelFrame>
  );
}
