import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, DatabaseZap, Loader2, Play } from "lucide-react";

import { api, ApiError, streamWorkspaceImport, type ImportEvent } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";

const SECTION_LABELS: Record<string, string> = {
  brand: "Brand",
  products: "Products",
  manufacturing: "Manufacturing",
  packaging: "Packaging",
  shopify: "Shopify",
  marketing: "Marketing",
  documents: "Documents",
};

/**
 * Populate this workspace from the sources it's connected to — the live
 * Shopify catalog, its Gmail, its Drive — into one searchable knowledge base,
 * with a link back to the original on every item.
 *
 * Additive by construction: items are only ever added, a section's notes are
 * only filled when empty, and re-running imports what's new rather than
 * duplicating what's here. Whatever couldn't be reached is reported as a gap
 * instead of being quietly skipped.
 */
export default function WorkspaceImportPage() {
  const { activeCompany, activeCompanyId } = useCompany();
  const toast = useToast();
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [result, setResult] = useState<ImportEvent | null>(null);
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof api.importSummary>> | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const loadSummary = useCallback(async () => {
    if (!activeCompanyId) return;
    try {
      setSummary(await api.importSummary(activeCompanyId));
    } catch {
      setSummary(null);
    }
  }, [activeCompanyId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);
  useEffect(() => () => abortRef.current?.(), []);

  function start() {
    if (!activeCompanyId || running) return;
    setRunning(true);
    setLog([]);
    setResult(null);
    abortRef.current = streamWorkspaceImport(activeCompanyId, {
      onEvent: (e) => {
        if (e.type === "progress" || e.type === "start") {
          setLog((prev) => [
            ...prev,
            e.type === "start" ? `Scanning ${e.workspace}…` : `${e.source}: ${e.message}`,
          ]);
        }
        if (e.type === "done") setResult(e);
      },
      onDone: async () => {
        setRunning(false);
        await loadSummary();
      },
      onError: (msg) => {
        setRunning(false);
        toast.push(msg, "error");
      },
    });
  }

  if (!activeCompanyId) {
    return (
      <main className="flex h-full flex-1 items-center justify-center p-6 text-center text-sm text-jarvis-muted">
        Select a workspace to import into.
      </main>
    );
  }

  return (
    <main className="h-full min-h-0 flex-1 space-y-4 overflow-y-auto p-4 pb-[max(6rem,calc(env(safe-area-inset-bottom)+5rem))] md:pb-4">
      <ModulePageHeader
        icon={DatabaseZap}
        title="Populate workspace"
        description={`Read ${activeCompany?.name ?? "this workspace"}'s connected Shopify store, Gmail and Drive into one searchable knowledge base. Nothing you've written is overwritten, and every item keeps a link to its original.`}
        sampleData={false}
      />

      <section className="hud-panel hud-corner p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-jarvis-text">
              {summary && summary.total > 0
                ? `${summary.total} items already indexed`
                : "Nothing imported yet"}
            </p>
            {summary && summary.total > 0 && (
              <p className="mt-0.5 text-[11px] text-jarvis-muted">
                {Object.entries(summary.by_source)
                  .map(([source, n]) => `${source.replace("import:", "")} ${n}`)
                  .join(" · ")}
              </p>
            )}
          </div>
          <button
            onClick={start}
            disabled={running}
            className="press-scale flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-jarvis-bg transition disabled:opacity-40"
            style={{ backgroundColor: "var(--ws-accent)" }}
          >
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {running ? "Scanning…" : summary && summary.total > 0 ? "Scan for new" : "Start import"}
          </button>
        </div>

        {log.length > 0 && (
          <ul className="mt-3 space-y-1 border-t border-jarvis-border/40 pt-3">
            {log.map((line, i) => (
              <li key={i} className="flex items-center gap-2 font-data text-[11px] text-jarvis-muted">
                {running && i === log.length - 1 ? (
                  <Loader2 className="h-3 w-3 shrink-0 animate-spin text-jarvis-cyan" />
                ) : (
                  <Check className="h-3 w-3 shrink-0 text-jarvis-emerald" />
                )}
                {line}
              </li>
            ))}
          </ul>
        )}
      </section>

      {result && (
        <section className="hud-panel hud-corner space-y-3 p-4">
          <p className="text-sm text-jarvis-text">
            Imported <span className="font-semibold">{result.imported}</span> new item
            {result.imported === 1 ? "" : "s"}
            {typeof result.already_had === "number" && result.already_had > 0 && (
              <span className="text-jarvis-muted"> · {result.already_had} already indexed</span>
            )}
            {typeof result.tasks_suggested === "number" && result.tasks_suggested > 0 && (
              <span className="text-jarvis-muted"> · {result.tasks_suggested} flagged for review</span>
            )}
          </p>

          {result.by_section && Object.keys(result.by_section).length > 0 && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(result.by_section).map(([section, n]) => (
                <div key={section} className="rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 p-2.5">
                  <p className="text-[10px] uppercase tracking-widest text-jarvis-faint">
                    {SECTION_LABELS[section] ?? section}
                  </p>
                  <p className="font-data text-sm text-jarvis-text">{n}</p>
                </div>
              ))}
            </div>
          )}

          {/* What couldn't be reached — stated, not hidden. */}
          {result.gaps && result.gaps.length > 0 && (
            <div>
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-jarvis-amber">
                <AlertTriangle className="h-3.5 w-3.5" /> Not available
              </p>
              <ul className="space-y-1">
                {result.gaps.map((gap, i) => (
                  <li key={i} className="text-[11px] text-jarvis-muted">
                    · {gap}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
