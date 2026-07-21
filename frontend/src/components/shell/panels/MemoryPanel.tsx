import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useProject } from "@/context/ProjectContext";
import PanelFrame, { PanelEmpty, PanelError, PanelLoading } from "@/components/shell/panels/PanelFrame";
import type { MemoryEntry } from "@/types";

// AI Memory for the active workspace — defaults to the active PROJECT's memory
// (the single source of truth), with a toggle to widen to the whole company.
// A search box runs the same natural-language search as the Memory page.
export default function MemoryPanel({ onClose }: { onClose: () => void }) {
  const { activeCompanyId } = useCompany();
  const { activeProject, activeProjectId } = useProject();
  const navigate = useNavigate();
  const [scope, setScope] = useState<"project" | "company">("project");
  const [q, setQ] = useState("");
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const useProjectScope = scope === "project" && activeProjectId;
      setEntries(
        await api.searchMemory({
          q: q.trim() || undefined,
          companyId: activeCompanyId ?? "any",
          projectId: useProjectScope ? activeProjectId : undefined,
          limit: 30,
        })
      );
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [q, scope, activeCompanyId, activeProjectId]);

  // Re-scope on company/project switch (and scope toggle); don't refire on every keystroke.
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, activeCompanyId, activeProjectId]);

  return (
    <PanelFrame
      title="AI Memory"
      icon={BrainCircuit}
      onClose={onClose}
      onRefresh={load}
      refreshing={loading}
      subtitle={scope === "project" ? (activeProject?.name ?? "No active project") : "This company"}
    >
      <div className="mb-3 space-y-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
          className="relative"
        >
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-jarvis-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search memory…"
            className="w-full rounded-lg border border-jarvis-border bg-jarvis-panel2/50 py-1.5 pl-8 pr-3 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
          />
        </form>
        <div className="flex gap-1">
          {(["project", "company"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setScope(s)}
              disabled={s === "project" && !activeProjectId}
              className={clsx(
                "rounded-lg px-2.5 py-1 text-xs capitalize transition-colors disabled:opacity-40",
                scope === s
                  ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                  : "text-jarvis-muted hover:text-jarvis-text"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <PanelLoading />
      ) : failed ? (
        <PanelError onRetry={load} />
      ) : entries.length === 0 ? (
        <PanelEmpty label="No memory yet." />
      ) : (
        <ul className="space-y-2">
          {entries.map((m) => (
            <li key={m.id}>
              <button
                onClick={() => navigate(`/memory?q=${encodeURIComponent(m.title)}`)}
                className="w-full rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 px-3 py-2.5 text-left transition-colors hover:border-jarvis-cyan/40"
              >
                <p className="truncate text-sm text-jarvis-text">{m.title}</p>
                <p className="mt-0.5 line-clamp-2 text-xs text-jarvis-muted">{m.content}</p>
                <p className="mt-1 text-[10px] uppercase tracking-wide text-jarvis-faint">
                  {m.kind} · {m.scope}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </PanelFrame>
  );
}
