import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Rocket, Trash2 } from "lucide-react";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import CompanyScopedPage from "@/components/CompanyScopedPage";
import ModulePageHeader from "@/components/ModulePageHeader";
import { usePrompt } from "@/context/PromptContext";
import { useToast } from "@/context/ToastContext";
import { PROJECT_COLUMNS } from "@/mock/projects";
import type { CompanyTask, ProjectStatus } from "@/types";

/**
 * Real, company-scoped kanban board — backed by the `tasks` table
 * (app/api/v1/endpoints/tasks.py), not mock data. Same 4-column layout and
 * card design as before; only the data source changed.
 */
export default function ProjectManagerPage() {
  return (
    <CompanyScopedPage>
      {(company) => <Board companyId={company.id} companyName={company.name} />}
    </CompanyScopedPage>
  );
}

function Board({ companyId, companyName }: { companyId: string; companyName: string }) {
  const [tasks, setTasks] = useState<CompanyTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [movingId, setMovingId] = useState<string | null>(null);
  const prompt = usePrompt();
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listCompanyTasks(companyId);
      setTasks(list);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to load tasks.", "error");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function moveCard(id: string, status: ProjectStatus) {
    setMovingId(id);
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, status } : t)));
    try {
      await api.updateCompanyTask(id, { status });
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to move task.", "error");
      load();
    } finally {
      setMovingId(null);
    }
  }

  async function removeCard(id: string) {
    setTasks((prev) => prev.filter((t) => t.id !== id));
    try {
      await api.deleteCompanyTask(id);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to delete task.", "error");
      load();
    }
  }

  async function addTask() {
    const values = await prompt({
      title: "New Task",
      fields: [
        { key: "title", label: "Title" },
        { key: "description", label: "Description", multiline: true },
        { key: "assignee", label: "Assignee (optional)" },
        { key: "dueDate", label: "Due date (optional, YYYY-MM-DD)" },
      ],
      confirmLabel: "Add",
    });
    if (values === null || !values.title.trim()) return;
    try {
      const task = await api.createCompanyTask(companyId, {
        title: values.title.trim(),
        description: values.description.trim() || undefined,
        assignee: values.assignee.trim() || undefined,
        due_date: values.dueDate.trim() || undefined,
        status: "backlog",
      });
      setTasks((prev) => [task, ...prev]);
      toast.push("Task added.", "success");
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to create task.", "error");
    }
  }

  return (
    <>
      <ModulePageHeader
        icon={Rocket}
        title="Project Manager"
        description={`Cross-functional project board for ${companyName}.`}
        sampleData={false}
        actions={
          <button
            onClick={addTask}
            className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
          >
            <Plus className="h-3.5 w-3.5" />
            New Task
          </button>
        }
      />

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PROJECT_COLUMNS.map((col) => {
            const items = tasks.filter((t) => t.status === col.key);
            return (
              <div key={col.key} className="hud-panel flex min-h-0 flex-col overflow-hidden">
                <div className="flex items-center justify-between border-b border-jarvis-border/70 px-4 py-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-jarvis-text">
                    {col.label}
                  </h3>
                  <span className="text-xs text-jarvis-muted">{items.length}</span>
                </div>
                <div className="flex-1 space-y-2 overflow-y-auto p-3">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className={clsx(
                        "rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/50 p-3 transition-opacity",
                        movingId === item.id && "opacity-50"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-jarvis-text">{item.title}</p>
                        <button
                          onClick={() => removeCard(item.id)}
                          title="Delete task"
                          className="press-scale shrink-0 rounded-md p-0.5 text-jarvis-faint transition hover:text-jarvis-rose"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                      {item.description && (
                        <p className="mt-1 text-xs leading-relaxed text-jarvis-muted">{item.description}</p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-jarvis-muted">
                        {item.division && (
                          <span className="rounded-full border border-jarvis-border/70 px-2 py-0.5">
                            {item.division}
                          </span>
                        )}
                        {item.assignee && (
                          <span className="rounded-full border border-jarvis-border/70 px-2 py-0.5">
                            {item.assignee}
                          </span>
                        )}
                        {item.due_date && (
                          <span className="rounded-full border border-jarvis-border/70 px-2 py-0.5">
                            Due {item.due_date}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 flex gap-1">
                        {PROJECT_COLUMNS.filter((c) => c.key !== item.status).map((c) => (
                          <button
                            key={c.key}
                            onClick={() => moveCard(item.id, c.key)}
                            className="rounded-md border border-transparent px-1.5 py-0.5 text-[10px] text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
                          >
                            → {c.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  {items.length === 0 && (
                    <p className="px-2 py-6 text-center text-xs text-jarvis-muted">Empty</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
