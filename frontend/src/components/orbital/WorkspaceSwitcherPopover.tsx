import { AnimatePresence, motion } from "framer-motion";
import { Building2, Check, FolderKanban, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useCompany } from "@/context/CompanyContext";
import { useProject } from "@/context/ProjectContext";
import { resolveWorkspace } from "@/lib/workspace";
import { usePrompt } from "@/context/PromptContext";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";

/**
 * The single control for "which company AND which project is active." Every
 * workspace-scoped orbital node re-renders against whichever company this
 * popover selects; every Quick Action attaches to whichever project it selects
 * (the two-level model — a business, and a shared Project within it). The
 * shell itself never branches per company/project, only the data underneath
 * it does.
 */
export default function WorkspaceSwitcherPopover({
  open,
  onClose,
  anchor,
}: {
  open: boolean;
  onClose: () => void;
  anchor: { x: number; y: number };
}) {
  const { companies, activeCompanyId, setActiveCompanyId, createCompany, loading } = useCompany();
  const {
    projects,
    activeProjectId,
    setActiveProjectId,
    createProject,
    loading: projectsLoading,
  } = useProject();
  const prompt = usePrompt();
  const toast = useToast();
  const navigate = useNavigate();

  async function handleNewCompany() {
    const values = await prompt({
      title: "New Workspace",
      fields: [{ key: "name", label: "Company name" }],
      confirmLabel: "Create",
    });
    if (values === null || !values.name.trim()) return;
    try {
      await createCompany(values.name.trim());
      onClose();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to create company.", "error");
    }
  }

  async function handleNewProject() {
    const values = await prompt({
      title: "New Project",
      fields: [{ key: "name", label: "Project name" }],
      confirmLabel: "Create",
    });
    if (values === null || !values.name.trim()) return;
    try {
      const project = await createProject(values.name.trim());
      onClose();
      navigate(`/projects/${project.id}`);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to create project.", "error");
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="hud-panel hud-corner fixed z-50 w-64 p-2"
            style={{ left: anchor.x, top: anchor.y, transform: "translate(-50%, 12px)" }}
          >
            <div className="flex items-center gap-2 border-b border-jarvis-border/60 px-2 pb-2">
              <Building2 className="h-3.5 w-3.5 text-jarvis-cyan" />
              <p className="text-[10px] font-semibold uppercase tracking-widest text-jarvis-muted">
                Switch Workspace
              </p>
            </div>
            <div className="max-h-48 overflow-y-auto py-1">
              {loading && <div className="skeleton m-2 h-9 rounded-lg" />}
              {!loading &&
                companies.map((c) => {
                  const ws = resolveWorkspace(c);
                  return (
                    <button
                      key={c.id}
                      onClick={() => {
                        setActiveCompanyId(c.id);
                        onClose();
                      }}
                      className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-jarvis-muted transition-colors duration-150 hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                    >
                      {/* Each workspace's own monogram "logo" in its accent. */}
                      <span
                        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg font-display text-[10px] font-bold"
                        style={{ backgroundColor: ws.theme.accentFaint, color: ws.theme.accent }}
                      >
                        {ws.monogram}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-jarvis-text">{c.name}</span>
                        <span className="block truncate text-[10px] text-jarvis-muted">{ws.role}</span>
                      </span>
                      {c.id === activeCompanyId && <Check className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan" />}
                    </button>
                  );
                })}
              {!loading && companies.length === 0 && (
                <p className="px-2.5 py-3 text-xs text-jarvis-muted">No workspaces yet.</p>
              )}
            </div>
            <button
              onClick={handleNewCompany}
              className="flex w-full items-center gap-2 rounded-lg border-t border-jarvis-border/60 px-2.5 py-2 pt-2.5 text-left text-sm text-jarvis-muted transition-colors duration-150 hover:text-jarvis-cyan"
            >
              <Plus className="h-3.5 w-3.5" />
              New Workspace
            </button>

            {/* Active project — the shared container Quick Actions attach to. */}
            <div className="mt-1 flex items-center gap-2 border-t border-jarvis-border/60 px-2 pb-2 pt-2.5">
              <FolderKanban className="h-3.5 w-3.5 text-jarvis-cyan" />
              <p className="text-[10px] font-semibold uppercase tracking-widest text-jarvis-muted">
                Active Project
              </p>
            </div>
            <div className="max-h-40 overflow-y-auto py-1">
              {projectsLoading && <div className="skeleton m-2 h-9 rounded-lg" />}
              {!projectsLoading &&
                projects.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setActiveProjectId(p.id);
                      onClose();
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-jarvis-muted transition-colors duration-150 hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  >
                    <span className="min-w-0 flex-1 truncate">{p.name}</span>
                    {p.is_default && (
                      <span className="shrink-0 rounded bg-jarvis-panel2 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-jarvis-muted">
                        default
                      </span>
                    )}
                    {p.id === activeProjectId && <Check className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan" />}
                  </button>
                ))}
              {!projectsLoading && projects.length === 0 && (
                <p className="px-2.5 py-3 text-xs text-jarvis-muted">No projects yet.</p>
              )}
            </div>
            <div className="flex items-center gap-1 border-t border-jarvis-border/60 pt-1">
              <button
                onClick={handleNewProject}
                className="flex flex-1 items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-jarvis-muted transition-colors duration-150 hover:text-jarvis-cyan"
              >
                <Plus className="h-3.5 w-3.5" />
                New Project
              </button>
              {activeProjectId && (
                <button
                  onClick={() => {
                    onClose();
                    navigate(`/projects/${activeProjectId}`);
                  }}
                  className="rounded-lg px-2.5 py-2 text-xs font-medium text-jarvis-cyan/80 transition-colors duration-150 hover:text-jarvis-cyan"
                >
                  Open →
                </button>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
