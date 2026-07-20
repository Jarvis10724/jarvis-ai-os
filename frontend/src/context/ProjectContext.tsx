import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ApiError } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { useCompany } from "@/context/CompanyContext";
import type { ProjectSummary } from "@/types";

// Active project is remembered PER company, so switching businesses restores
// whichever project you last had open in that business (falling back to its
// default). Namespacing the key by company id is what makes that work.
const activeProjectKey = (companyId: string | null) =>
  `jarvis_active_project_id_${companyId ?? "none"}`;

interface ProjectContextValue {
  projects: ProjectSummary[];
  activeProject: ProjectSummary | null;
  activeProjectId: string | null;
  loading: boolean;
  error: string | null;
  setActiveProjectId: (id: string) => void;
  createProject: (name: string) => Promise<ProjectSummary>;
  refresh: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

// Nested under CompanyContext: a business (Company) is the switchable
// workspace, and within it a Project is the shared container every Quick
// Action attaches to. This context is the single source of truth for "which
// project is active" for the current business. When the active company
// changes, the whole project list re-scopes — this is what makes switching a
// business instantly switch all associated project data.
export function ProjectProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { activeCompanyId } = useCompany();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function setActiveProjectId(id: string) {
    setActiveProjectIdState(id);
    localStorage.setItem(activeProjectKey(activeCompanyId), id);
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const scope = activeCompanyId ?? "none";
      // Make sure the business has a default project before listing, so a
      // brand-new company always has at least one project to attach to.
      await api.getDefaultProject(activeCompanyId).catch(() => null);
      const list = await api.listProjects(scope);
      setProjects(list);

      const stored = localStorage.getItem(activeProjectKey(activeCompanyId));
      const stillValid = stored && list.some((p) => p.id === stored);
      const fallback = list.find((p) => p.is_default)?.id ?? list[0]?.id ?? null;
      const next = stillValid ? stored : fallback;
      setActiveProjectIdState(next);
      if (next) localStorage.setItem(activeProjectKey(activeCompanyId), next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }

  async function createProject(name: string) {
    const project = await api.createProject({ name, company_id: activeCompanyId });
    setProjects((prev) => [...prev, project]);
    setActiveProjectId(project.id);
    return project;
  }

  // Re-scope whenever the user or the active business changes.
  useEffect(() => {
    if (user) {
      refresh();
    } else {
      setProjects([]);
      setActiveProjectIdState(null);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, activeCompanyId]);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        activeProjectId,
        loading,
        error,
        setActiveProjectId,
        createProject,
        refresh,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
