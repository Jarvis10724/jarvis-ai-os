import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import clsx from "clsx";

import { api } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useProject } from "@/context/ProjectContext";
import { SEVERITY_ICON, SEVERITY_STYLES } from "@/components/NotificationsPanel";
import PanelFrame, { PanelEmpty, PanelLoading } from "@/components/shell/panels/PanelFrame";
import type { NotificationItem } from "@/types";

// Internal: carry a sortable timestamp alongside the display item.
type Note = NotificationItem & { _ts: string | null };

function ago(iso: string | null): string {
  if (!iso) return "";
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}

// The Notification Center — REAL, no backend changes. Aggregates live signals
// for the active workspace from existing endpoints: pending approvals, active
// agent runs, and recent project-timeline activity. Scoped to the active
// company/project (the single source of truth).
export default function NotificationsCenter({ onClose }: { onClose: () => void }) {
  const { activeCompanyId } = useCompany();
  const { activeProjectId } = useProject();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [approvals, agentRuns, timeline] = await Promise.all([
        api.listApprovals({ companyId: activeCompanyId ?? "any", status: "pending" }).catch(() => []),
        api.listAgentRuns({ companyId: activeCompanyId ?? "none" }).catch(() => []),
        activeProjectId ? api.getProjectTimeline(activeProjectId, 20).catch(() => []) : Promise.resolve([]),
      ]);

      const notes: Note[] = [];

      for (const a of approvals) {
        notes.push({
          id: `approval-${a.id}`,
          title: `Approval needed: ${a.capability_name}`,
          description: `${a.action_type} is waiting for your decision.`,
          time: ago(a.created_at),
          severity: "warning",
          read: false,
          _ts: a.created_at,
        });
      }

      for (const r of agentRuns) {
        if (r.status === "failed") {
          notes.push({
            id: `agent-${r.id}`,
            title: `Agent failed: ${r.agent_label}`,
            description: r.objective,
            time: ago(r.updated_at),
            severity: "critical",
            read: false,
            _ts: r.updated_at,
          });
        } else if (r.status === "running" || r.status === "awaiting_approval" || r.status === "queued") {
          notes.push({
            id: `agent-${r.id}`,
            title: `Agent ${r.status.replace(/_/g, " ")}: ${r.agent_label}`,
            description: r.objective,
            time: ago(r.updated_at),
            severity: r.status === "awaiting_approval" ? "warning" : "info",
            read: false,
            _ts: r.updated_at,
          });
        }
      }

      for (const e of timeline.slice(0, 8)) {
        notes.push({
          id: `event-${e.id}`,
          title: e.title,
          description: e.detail ?? e.kind.replace(/_/g, " "),
          time: ago(e.created_at),
          severity: e.kind === "website_built" ? "success" : "info",
          read: true,
          _ts: e.created_at,
        });
      }

      notes.sort((a, b) => (b._ts ?? "").localeCompare(a._ts ?? ""));
      setItems(notes.slice(0, 30));
    } finally {
      setLoading(false);
    }
  }, [activeCompanyId, activeProjectId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PanelFrame title="Notifications" icon={Bell} onClose={onClose} onRefresh={load} refreshing={loading}>
      {loading ? (
        <PanelLoading />
      ) : items.length === 0 ? (
        <PanelEmpty label="All clear — nothing needs your attention." />
      ) : (
        <ul className="space-y-2">
          {items.map((n) => {
            const Icon = SEVERITY_ICON[n.severity];
            return (
              <li
                key={n.id}
                className={clsx(
                  "rounded-xl border p-3",
                  n.read ? "border-jarvis-border/40 bg-jarvis-panel2/25" : "border-jarvis-border/70 bg-jarvis-panel2/50"
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
                    <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-jarvis-muted">
                      {n.description}
                    </p>
                    <p className="mt-1 text-[10px] uppercase tracking-wide text-jarvis-faint">{n.time}</p>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </PanelFrame>
  );
}
