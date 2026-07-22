import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, FolderKanban, Plus } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import clsx from "clsx";

import { useProject } from "@/context/ProjectContext";
import { usePrompt } from "@/context/PromptContext";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";

// The active-project picker for the current business. Sits directly under the
// CompanySwitcher: pick which shared Project every Quick Action attaches to.
export default function ProjectSwitcher({ onNavigate }: { onNavigate?: () => void } = {}) {
  const { projects, activeProject, activeProjectId, setActiveProjectId, createProject, loading } =
    useProject();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const prompt = usePrompt();
  const toast = useToast();
  const navigate = useNavigate();

  async function handleNewProject() {
    const values = await prompt({
      title: "New Project",
      fields: [{ key: "name", label: "Project name" }],
      confirmLabel: "Create",
    });
    if (values === null || !values.name.trim()) return;
    try {
      const project = await createProject(values.name.trim());
      setOpen(false);
      navigate(`/projects/${project.id}`);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to create project.", "error");
    }
  }

  if (loading) {
    return <div className="skeleton mx-4 mt-2 h-9 rounded-xl" />;
  }

  if (!activeProject) {
    return null;
  }

  return (
    <div className="relative mx-3 mt-2 shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-xl border border-jarvis-border bg-jarvis-panel2/30 px-3 py-2 text-left transition-all duration-200 hover:border-jarvis-cyan/40"
      >
        <FolderKanban className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan/80" />
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-jarvis-text">
          {activeProject.name}
        </span>
        <ChevronDown
          className={clsx(
            "h-3 w-3 shrink-0 text-jarvis-muted transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              className="absolute left-0 right-0 z-40 mt-1.5 max-h-72 overflow-y-auto rounded-xl border border-jarvis-border bg-jarvis-panel/95 p-1.5 shadow-elevated-lg backdrop-blur-2xl"
            >
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setActiveProjectId(p.id);
                    setOpen(false);
                  }}
                  className={clsx(
                    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-150",
                    p.id === activeProjectId
                      ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                      : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">{p.name}</span>
                  {p.is_default && (
                    <span className="shrink-0 rounded bg-jarvis-panel2 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-jarvis-muted">
                      default
                    </span>
                  )}
                </button>
              ))}
              <button
                onClick={handleNewProject}
                className="mt-1 flex w-full items-center gap-2 rounded-lg border-t border-jarvis-border/60 px-3 py-2 pt-2.5 text-left text-sm text-jarvis-muted transition-colors duration-150 hover:text-jarvis-cyan"
              >
                <Plus className="h-3.5 w-3.5" />
                New Project
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Hidden when you're already in this project's workspace — an inert
          control. Closes the mobile drawer on the way so the workspace it
          opens isn't left underneath it. */}
      {pathname !== `/projects/${activeProject.id}` && (
        <button
          onClick={() => {
            navigate(`/projects/${activeProject.id}`);
            onNavigate?.();
          }}
          className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-[11px] font-medium text-jarvis-muted transition-colors duration-150 hover:text-jarvis-cyan"
        >
          Open Project Workspace →
        </button>
      )}
    </div>
  );
}
