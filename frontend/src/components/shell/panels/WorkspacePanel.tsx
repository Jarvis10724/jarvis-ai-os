import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, LayoutGrid, Network } from "lucide-react";

import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useWorkspace } from "@/hooks/useWorkspace";
import { domainsForKind } from "@/lib/workspace";
import PanelFrame, { PanelEmpty } from "@/components/shell/panels/PanelFrame";
import { useSyncedResource } from "@/context/SyncContext";

/**
 * The Workspace universe — the "this workspace is a complete AI operating
 * environment" surface. Shows the workspace's identity (monogram logo, kind,
 * parent) and every domain of its environment (memory, files, mail, calendar,
 * integrations, brand, tasks, approvals, agents, conversations) with live
 * status, each a tap into that domain. Everything is scoped to the active
 * workspace and re-scopes on switch; the domain list comes from the scalable
 * WORKSPACE_DOMAINS registry so new domains/integrations appear here for free.
 */
export default function WorkspacePanel({ onClose }: { onClose: () => void }) {
  const { activeCompany, activeCompanyId } = useCompany();
  const workspace = useWorkspace();
  const navigate = useNavigate();

  const [status, setStatus] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!activeCompanyId) {
      setStatus({});
      setLoading(false);
      return;
    }
    setLoading(true);
    const next: Record<string, string> = {};
    // Each domain's live status is best-effort — one failing call must not
    // blank the whole universe view, so they're gathered independently.
    await Promise.allSettled([
      api.searchMemory({ companyId: activeCompanyId, limit: 100 }).then((m) => {
        next.memory = `${m.length}${m.length === 100 ? "+" : ""} ${m.length === 1 ? "memory" : "memories"}`;
      }),
      api.listApprovals({ companyId: activeCompanyId, status: "pending" }).then((a) => {
        next.approvals = a.length > 0 ? `${a.length} pending` : "All clear";
      }),
      api.listIntegrations(activeCompanyId).then((list) => {
        const connected = list.filter((i) => i.connected);
        next.integrations = `${connected.length}/${list.length} connected`;
        next.mail = list.find((i) => i.name === "email")?.connected ? "Connected" : "Not connected";
        next.calendar = list.find((i) => i.name === "google_calendar")?.connected
          ? "Connected"
          : "Not connected";
      }),
    ]).catch(() => {
      /* handled per-promise above */
    });
    setStatus(next);
    setLoading(false);
  }, [activeCompanyId]);

  // Re-read whenever this kind of state changes anywhere — any device,
  // any origin (a person, an agent, an integration). No timer here.
  useSyncedResource("workspace", load);

  useEffect(() => {
    load();
  }, [load]);

  const domains = domainsForKind(workspace.kind);

  function go(path: string) {
    navigate(path);
    onClose();
  }

  return (
    <PanelFrame
      title="Workspace"
      icon={LayoutGrid}
      onClose={onClose}
      onRefresh={load}
      refreshing={loading}
      subtitle={activeCompany ? workspace.role : "No active workspace"}
    >
      {!activeCompany ? (
        <PanelEmpty label="No active workspace." />
      ) : (
        <>
          {/* Identity — the workspace as its own operating environment. */}
          <div
            className="mb-4 rounded-2xl border p-4"
            style={{ borderColor: "var(--ws-accent-soft)", backgroundColor: "var(--ws-accent-faint)" }}
          >
            <div className="flex items-center gap-3">
              <span
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl font-display text-lg font-bold shadow-glow-sm"
                style={{ backgroundColor: "var(--ws-accent-faint)", color: "var(--ws-accent)", borderColor: "var(--ws-accent-soft)" }}
              >
                {workspace.monogram}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-jarvis-text">{activeCompany.name}</p>
                <p className="truncate text-xs" style={{ color: "var(--ws-accent)" }}>
                  {workspace.role}
                </p>
                {activeCompany.parent_company_name && (
                  <p className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-jarvis-muted">
                    <Network className="h-3 w-3 shrink-0" />
                    Part of {activeCompany.parent_company_name}
                  </p>
                )}
              </div>
            </div>
            <p className="mt-2.5 text-[11px] leading-relaxed text-jarvis-muted">{workspace.purpose}</p>
          </div>

          <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-jarvis-faint">
            Operating environment
          </p>
          <ul className="space-y-1.5">
            {domains.map((d) => {
              const Icon = d.icon;
              const stat = status[d.key];
              return (
                <li key={d.key}>
                  <button
                    onClick={() => go(d.route(activeCompanyId))}
                    className="group flex w-full items-center gap-3 rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 px-3 py-2.5 text-left transition-colors hover:border-[color:var(--ws-accent-soft)]"
                  >
                    <span
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-jarvis-panel3/50"
                      style={{ color: "var(--ws-accent)" }}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-jarvis-text">{d.label}</span>
                      <span className="block truncate text-[11px] text-jarvis-muted">
                        {stat ?? d.description}
                      </span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-jarvis-faint transition-colors group-hover:text-jarvis-text" />
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </PanelFrame>
  );
}
