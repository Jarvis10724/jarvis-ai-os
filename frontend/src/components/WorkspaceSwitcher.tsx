import { AnimatePresence, motion } from "framer-motion";
import { Check, Network, Plus } from "lucide-react";

import { useCompany } from "@/context/CompanyContext";
import { usePrompt } from "@/context/PromptContext";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";
import { resolveWorkspace } from "@/lib/workspace";

/**
 * Global workspace switcher — reachable from the top bar on every screen, so
 * switching between Greener Capitol, Primal Penni, and future businesses is a
 * first-class action, not buried in the Home. Each workspace shows its own
 * monogram + accent + kind, and its parent org when one exists (the
 * parent_company metadata), so the org structure is visible at a glance.
 *
 * Switching is instant and state-preserving: it only sets the active company
 * (CompanyContext), which re-scopes every workspace surface — memory, Brand
 * Brain, approvals, integrations, the accent cross-fade — without navigating or
 * losing the current screen. Real functionality, not a reskin.
 */
export default function WorkspaceSwitcher({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { companies, activeCompanyId, setActiveCompanyId, createCompany, loading } = useCompany();
  const prompt = usePrompt();
  const toast = useToast();

  async function handleNew() {
    const values = await prompt({
      title: "New workspace",
      fields: [{ key: "name", label: "Business / workspace name" }],
      confirmLabel: "Create",
    });
    if (values === null || !values.name.trim()) return;
    try {
      await createCompany(values.name.trim());
      onClose();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to create workspace.", "error");
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.98 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-x-0 bottom-0 z-[61] mx-auto flex max-h-[80vh] w-full max-w-md flex-col rounded-t-3xl border border-jarvis-border/70 bg-jarvis-panel/95 pb-safe backdrop-blur-2xl shadow-elevated-lg sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-24 sm:-translate-x-1/2 sm:rounded-3xl"
          >
            <div className="border-b border-jarvis-border/50 px-4 py-3">
              <p className="font-display text-sm font-semibold tracking-wide text-jarvis-text">Switch workspace</p>
              <p className="text-[11px] text-jarvis-muted">Each is its own AI operating environment.</p>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {loading && <div className="skeleton m-2 h-14 rounded-xl" />}
              {!loading &&
                companies.map((c) => {
                  const ws = resolveWorkspace(c);
                  const active = c.id === activeCompanyId;
                  return (
                    <button
                      key={c.id}
                      onClick={() => {
                        setActiveCompanyId(c.id);
                        onClose();
                      }}
                      className="group flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors hover:bg-jarvis-panel2/50"
                    >
                      <span
                        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl font-display text-sm font-bold"
                        style={{ backgroundColor: ws.theme.accentFaint, color: ws.theme.accent }}
                      >
                        {ws.monogram}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-jarvis-text">{c.name}</span>
                        <span className="block truncate text-[11px] text-jarvis-muted">{ws.role}</span>
                        {c.parent_company_name && (
                          <span className="mt-0.5 flex items-center gap-1 truncate text-[10px] text-jarvis-faint">
                            <Network className="h-2.5 w-2.5 shrink-0" />
                            Part of {c.parent_company_name}
                          </span>
                        )}
                      </span>
                      {active && (
                        <span
                          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                          style={{ backgroundColor: ws.theme.accentFaint, color: ws.theme.accent }}
                        >
                          <Check className="h-3.5 w-3.5" />
                        </span>
                      )}
                    </button>
                  );
                })}
              {!loading && companies.length === 0 && (
                <p className="px-3 py-8 text-center text-sm text-jarvis-muted">No workspaces yet.</p>
              )}
            </div>

            <button
              onClick={handleNew}
              className="press-scale m-2 flex items-center justify-center gap-2 rounded-2xl border border-jarvis-border/70 bg-jarvis-panel2/30 py-3 text-sm font-medium text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
            >
              <Plus className="h-4 w-4" /> New workspace
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
