import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ArrowRightLeft,
  BrainCircuit,
  ChevronDown,
  History,
  Link2,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import ModulePageHeader from "@/components/ModulePageHeader";
import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import type {
  MemoryAuditEntry,
  MemoryEntry,
  MemoryEntryDetail,
  MemoryKind,
  MemoryScope,
  ProjectSummary,
} from "@/types";

const AUDIT_ACTION_LABELS: Record<MemoryAuditEntry["action"], string> = {
  created: "Created",
  updated: "Edited",
  scope_changed: "Scope changed",
  deleted: "Deleted",
};

const KIND_LABELS: Record<MemoryKind, string> = {
  conversation: "Conversation",
  email: "Email",
  meeting: "Meeting",
  quote: "Quote",
  sop: "SOP",
  decision: "Decision",
  contact: "Contact",
  product: "Product",
  goal: "Goal",
  task: "Task",
  file: "File",
  fact: "Fact",
  other: "Other",
};

const ALL_KINDS = Object.keys(KIND_LABELS) as MemoryKind[];

const SCOPE_LABELS: Record<MemoryScope, string> = {
  global: "Global",
  organization: "Organization",
  company: "Company",
  project: "Project",
  personal: "Personal",
};

const ALL_SCOPES = Object.keys(SCOPE_LABELS) as MemoryScope[];

// scope drives whether company/project pickers are relevant at all.
const SCOPE_NEEDS_COMPANY: Record<MemoryScope, boolean> = {
  global: false,
  organization: false,
  company: true,
  project: false, // optional, not required
  personal: false,
};
const SCOPE_NEEDS_PROJECT: Record<MemoryScope, boolean> = {
  global: false,
  organization: false,
  company: false,
  project: true,
  personal: false,
};

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

export default function MemoryPage() {
  const { companies } = useCompany();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [companyFilter, setCompanyFilter] = useState<string>(searchParams.get("company") ?? "any");
  const [kindFilter, setKindFilter] = useState<string>("");
  const [scopeFilter, setScopeFilter] = useState<string>("");
  const [results, setResults] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<MemoryEntryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editKind, setEditKind] = useState<MemoryKind>("fact");
  const [editSaving, setEditSaving] = useState(false);

  const [moving, setMoving] = useState(false);
  const [moveScope, setMoveScope] = useState<MemoryScope>("organization");
  const [moveCompany, setMoveCompany] = useState("");
  const [moveProject, setMoveProject] = useState("");
  const [moveNote, setMoveNote] = useState("");
  const [moveSaving, setMoveSaving] = useState(false);

  const [auditOpen, setAuditOpen] = useState(false);
  const [auditEntries, setAuditEntries] = useState<MemoryAuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  const [projects, setProjects] = useState<ProjectSummary[]>([]);

  // Every time a different entry is opened, any in-progress edit/move form
  // or expanded history from the previous one should not carry over.
  useEffect(() => {
    setEditing(false);
    setMoving(false);
    setAuditOpen(false);
    setAuditEntries([]);
  }, [selected?.id]);

  const [showAddForm, setShowAddForm] = useState(false);
  const [addKind, setAddKind] = useState<MemoryKind>("fact");
  const [addScope, setAddScope] = useState<MemoryScope>("organization");
  const [addCompany, setAddCompany] = useState<string>("");
  const [addProject, setAddProject] = useState<string>("");
  const [addTitle, setAddTitle] = useState("");
  const [addContent, setAddContent] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  const runSearch = useCallback(
    async (q: string) => {
      setLoading(true);
      setError(null);
      try {
        const list = await api.searchMemory({
          q,
          companyId: companyFilter as "any" | "global" | string,
          kind: kindFilter ? (kindFilter as MemoryKind) : undefined,
          scope: scopeFilter ? (scopeFilter as MemoryScope) : undefined,
          limit: 40,
        });
        setResults(list);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to search memory.");
      } finally {
        setLoading(false);
      }
    },
    [companyFilter, kindFilter, scopeFilter]
  );

  useEffect(() => {
    runSearch(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyFilter, kindFilter, scopeFilter]);

  useEffect(() => {
    // Run once on mount for a ?q= deep link (e.g. from the top nav search bar).
    runSearch(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSearchParams(query ? { q: query } : {});
    runSearch(query);
  }

  async function openEntry(id: string) {
    setDetailLoading(true);
    try {
      const detail = await api.getMemoryEntry(id);
      setSelected(detail);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't load that memory entry.", "error");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteMemory(id);
      setResults((prev) => prev.filter((r) => r.id !== id));
      setSelected(null);
      toast.push("Memory entry deleted.", "success");
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't delete that entry.", "error");
    }
  }

  function openEdit() {
    if (!selected) return;
    setEditTitle(selected.title);
    setEditContent(selected.content);
    setEditKind(selected.kind);
    setMoving(false);
    setEditing(true);
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !editTitle.trim() || !editContent.trim()) return;
    setEditSaving(true);
    try {
      const updated = await api.updateMemory(selected.id, {
        title: editTitle.trim(),
        content: editContent.trim(),
        kind: editKind,
      });
      setSelected({ ...selected, ...updated });
      setResults((prev) => prev.map((r) => (r.id === updated.id ? { ...r, ...updated } : r)));
      setEditing(false);
      toast.push("Memory updated.", "success");
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't save that edit.", "error");
    } finally {
      setEditSaving(false);
    }
  }

  function openMove() {
    if (!selected) return;
    setMoveScope(selected.scope);
    setMoveCompany(selected.company_id ?? "");
    setMoveProject(selected.project_id ?? "");
    setMoveNote("");
    setEditing(false);
    setMoving(true);
  }

  function handleMoveScopeChange(scope: MemoryScope) {
    setMoveScope(scope);
    if (!SCOPE_NEEDS_COMPANY[scope]) setMoveCompany("");
    if (!SCOPE_NEEDS_PROJECT[scope]) setMoveProject("");
  }

  async function handleMoveSave(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    if (SCOPE_NEEDS_COMPANY[moveScope] && !moveCompany) {
      toast.push("Pick a company for a company-scoped memory.", "error");
      return;
    }
    if (SCOPE_NEEDS_PROJECT[moveScope] && !moveProject) {
      toast.push("Pick a project for a project-scoped memory.", "error");
      return;
    }
    setMoveSaving(true);
    try {
      const updated = await api.moveMemoryScope(selected.id, {
        scope: moveScope,
        company_id: moveCompany || null,
        project_id: moveProject || null,
        note: moveNote.trim() || undefined,
      });
      setSelected({ ...selected, ...updated });
      setResults((prev) => prev.map((r) => (r.id === updated.id ? { ...r, ...updated } : r)));
      setMoving(false);
      toast.push(`Moved to ${SCOPE_LABELS[updated.scope]}.`, "success");
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't move that entry.", "error");
    } finally {
      setMoveSaving(false);
    }
  }

  async function toggleAudit() {
    if (!selected) return;
    const next = !auditOpen;
    setAuditOpen(next);
    if (next && auditEntries.length === 0) {
      setAuditLoading(true);
      try {
        const rows = await api.getMemoryAudit(selected.id);
        setAuditEntries(rows);
      } catch (err) {
        toast.push(err instanceof ApiError ? err.message : "Couldn't load history.", "error");
      } finally {
        setAuditLoading(false);
      }
    }
  }

  function handleScopeChange(scope: MemoryScope) {
    setAddScope(scope);
    if (!SCOPE_NEEDS_COMPANY[scope]) setAddCompany("");
    if (!SCOPE_NEEDS_PROJECT[scope]) setAddProject("");
  }

  async function handleAddSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!addTitle.trim() || !addContent.trim()) return;
    if (SCOPE_NEEDS_COMPANY[addScope] && !addCompany) {
      toast.push("Pick a company for a company-scoped memory.", "error");
      return;
    }
    if (SCOPE_NEEDS_PROJECT[addScope] && !addProject) {
      toast.push("Pick a project for a project-scoped memory.", "error");
      return;
    }
    setSaving(true);
    try {
      await api.createMemory({
        kind: addKind,
        title: addTitle.trim(),
        content: addContent.trim(),
        scope: addScope,
        company_id: addCompany || null,
        project_id: addProject || null,
        source: "manual",
      });
      setAddTitle("");
      setAddContent("");
      setShowAddForm(false);
      toast.push("Saved to memory.", "success");
      runSearch(query);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't save that.", "error");
    } finally {
      setSaving(false);
    }
  }

  function companyName(id: string | null): string | null {
    if (!id) return null;
    return companies.find((c) => c.id === id)?.name ?? "Unknown company";
  }

  function projectName(id: string | null): string | null {
    if (!id) return null;
    return projects.find((p) => p.id === id)?.name ?? "Unknown project";
  }

  function locationLabel(companyId: string | null, projectId: string | null): string | null {
    const parts = [companyName(companyId), projectName(projectId)].filter(Boolean);
    return parts.length ? parts.join(" · ") : null;
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={BrainCircuit}
          title="Memory"
          description="Jarvis's long-term brain — every conversation, quote, decision, contact, and business fact, scoped as Global, Organization, Company, Project, or Personal, and searchable by natural language."
          sampleData={false}
          actions={
            <button
              onClick={() => setShowAddForm((v) => !v)}
              className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Memory
            </button>
          }
        />

        {showAddForm && (
          <motion.form
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            onSubmit={handleAddSubmit}
            className="hud-panel hud-corner flex flex-col gap-3 p-5"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                value={addTitle}
                onChange={(e) => setAddTitle(e.target.value)}
                placeholder="Title"
                required
                className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3.5 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
              />
              <div className="flex gap-2">
                <select
                  value={addKind}
                  onChange={(e) => setAddKind(e.target.value as MemoryKind)}
                  className="flex-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
                >
                  {ALL_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {KIND_LABELS[k]}
                    </option>
                  ))}
                </select>
                <select
                  value={addScope}
                  onChange={(e) => handleScopeChange(e.target.value as MemoryScope)}
                  className="flex-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
                >
                  {ALL_SCOPES.map((s) => (
                    <option key={s} value={s}>
                      {SCOPE_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>
              {SCOPE_NEEDS_COMPANY[addScope] && (
                <select
                  value={addCompany}
                  onChange={(e) => setAddCompany(e.target.value)}
                  required
                  className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none sm:col-span-2"
                >
                  <option value="">Which company?</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              )}
              {SCOPE_NEEDS_PROJECT[addScope] && (
                <select
                  value={addProject}
                  onChange={(e) => setAddProject(e.target.value)}
                  required
                  className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none sm:col-span-2"
                >
                  <option value="">Which project?</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <textarea
              value={addContent}
              onChange={(e) => setAddContent(e.target.value)}
              placeholder="Details..."
              required
              rows={3}
              className="resize-none rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3.5 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="press-scale rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-4 py-2 text-sm font-medium text-jarvis-muted transition hover:text-jarvis-text"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="press-scale rounded-xl border border-jarvis-cyan/50 bg-jarvis-cyan/10 px-4 py-2 text-sm font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </motion.form>
        )}

        <form onSubmit={handleSearchSubmit} className="hud-panel hud-corner flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-jarvis-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search memory by natural language..."
              className="w-full rounded-xl border border-jarvis-border bg-jarvis-panel2/50 py-2.5 pl-9 pr-4 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
            />
          </div>
          <select
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
          >
            <option value="any">All memory</option>
            <option value="global">Not company-specific (Global/Org/Personal)</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
          >
            <option value="">Any kind</option>
            {ALL_KINDS.map((k) => (
              <option key={k} value={k}>
                {KIND_LABELS[k]}
              </option>
            ))}
          </select>
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
          >
            <option value="">Any scope</option>
            {ALL_SCOPES.map((s) => (
              <option key={s} value={s}>
                {SCOPE_LABELS[s]}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="press-scale rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-4 py-2.5 text-sm font-medium text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
          >
            Search
          </button>
        </form>

        <div className="hud-panel hud-corner flex min-h-0 flex-1 overflow-hidden">
          <div className={clsx("flex min-h-0 flex-1 flex-col overflow-y-auto", selected && "hidden md:flex md:max-w-md md:border-r md:border-jarvis-border/60")}>
            {loading ? (
              <div className="space-y-3 p-5">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="skeleton h-20 w-full" />
                ))}
              </div>
            ) : error ? (
              <p className="p-5 text-sm text-jarvis-rose">{error}</p>
            ) : results.length === 0 ? (
              <p className="p-5 text-sm text-jarvis-muted">
                Nothing found yet — memory fills in automatically as you chat with Jarvis, or add something above.
              </p>
            ) : (
              <ul className="divide-y divide-jarvis-border/40">
                {results.map((entry, i) => (
                  <motion.li
                    key={entry.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(i, 8) * 0.03, duration: 0.25 }}
                  >
                    <button
                      onClick={() => openEntry(entry.id)}
                      className={clsx(
                        "flex w-full flex-col gap-1 px-5 py-3.5 text-left transition-colors duration-150 hover:bg-jarvis-panel2/40",
                        selected?.id === entry.id && "bg-jarvis-cyan/5"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span className="rounded-full border border-jarvis-cyan/30 bg-jarvis-cyan/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-cyan">
                          {KIND_LABELS[entry.kind]}
                        </span>
                        <span className="rounded-full border border-jarvis-violet/30 bg-jarvis-violet/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-violet">
                          {SCOPE_LABELS[entry.scope]}
                        </span>
                        {locationLabel(entry.company_id, entry.project_id) && (
                          <span className="truncate text-xs text-jarvis-muted">
                            {locationLabel(entry.company_id, entry.project_id)}
                          </span>
                        )}
                        <span className="ml-auto shrink-0 text-[10px] text-jarvis-faint">{timeAgo(entry.created_at)}</span>
                      </div>
                      <p className="truncate text-sm font-medium text-jarvis-text">{entry.title}</p>
                      <p className="line-clamp-2 text-xs text-jarvis-muted">{entry.content}</p>
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </div>

          {selected && (
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-5">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-jarvis-cyan/30 bg-jarvis-cyan/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-cyan">
                      {KIND_LABELS[selected.kind]}
                    </span>
                    <span className="rounded-full border border-jarvis-violet/30 bg-jarvis-violet/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-violet">
                      {SCOPE_LABELS[selected.scope]}
                    </span>
                    {locationLabel(selected.company_id, selected.project_id) && (
                      <span className="text-xs text-jarvis-muted">
                        {locationLabel(selected.company_id, selected.project_id)}
                      </span>
                    )}
                  </div>
                  <h2 className="mt-1 text-base font-semibold text-jarvis-text">{selected.title}</h2>
                  <p className="text-xs text-jarvis-faint">
                    {selected.source} · {timeAgo(selected.created_at)}
                    {selected.confidence !== null && ` · ${Math.round(selected.confidence * 100)}% confidence`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={openEdit}
                    title="Edit this memory"
                    className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-cyan/10 hover:text-jarvis-cyan"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={openMove}
                    title="Move to a different scope"
                    className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-violet/10 hover:text-jarvis-violet"
                  >
                    <ArrowRightLeft className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(selected.id)}
                    title="Delete this memory"
                    className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-rose/10 hover:text-jarvis-rose"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setSelected(null)}
                    className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {editing ? (
                <form onSubmit={handleEditSave} className="flex flex-col gap-2.5 rounded-xl border border-jarvis-cyan/30 bg-jarvis-cyan/[0.03] p-3.5">
                  <div className="flex gap-2">
                    <input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      required
                      className="flex-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
                    />
                    <select
                      value={editKind}
                      onChange={(e) => setEditKind(e.target.value as MemoryKind)}
                      className="rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-2 py-2 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
                    >
                      {ALL_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {KIND_LABELS[k]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    required
                    rows={4}
                    className="resize-none rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setEditing(false)}
                      className="press-scale rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-1.5 text-xs font-medium text-jarvis-muted transition hover:text-jarvis-text"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={editSaving}
                      className="press-scale rounded-lg border border-jarvis-cyan/50 bg-jarvis-cyan/10 px-3 py-1.5 text-xs font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
                    >
                      {editSaving ? "Saving..." : "Save"}
                    </button>
                  </div>
                </form>
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-jarvis-text">{selected.content}</p>
              )}

              {moving && (
                <form
                  onSubmit={handleMoveSave}
                  className="mt-3 flex flex-col gap-2.5 rounded-xl border border-jarvis-violet/30 bg-jarvis-violet/[0.03] p-3.5"
                >
                  <p className="text-xs text-jarvis-muted">
                    Currently <span className="text-jarvis-violet">{SCOPE_LABELS[selected.scope]}</span>
                    {locationLabel(selected.company_id, selected.project_id) &&
                      ` (${locationLabel(selected.company_id, selected.project_id)})`}
                    . Moving is logged in this memory's history.
                  </p>
                  <select
                    value={moveScope}
                    onChange={(e) => handleMoveScopeChange(e.target.value as MemoryScope)}
                    className="rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text focus:border-jarvis-violet/50 focus:outline-none"
                  >
                    {ALL_SCOPES.map((s) => (
                      <option key={s} value={s}>
                        {SCOPE_LABELS[s]}
                      </option>
                    ))}
                  </select>
                  {SCOPE_NEEDS_COMPANY[moveScope] && (
                    <select
                      value={moveCompany}
                      onChange={(e) => setMoveCompany(e.target.value)}
                      required
                      className="rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text focus:border-jarvis-violet/50 focus:outline-none"
                    >
                      <option value="">Which company?</option>
                      {companies.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  )}
                  {SCOPE_NEEDS_PROJECT[moveScope] && (
                    <select
                      value={moveProject}
                      onChange={(e) => setMoveProject(e.target.value)}
                      required
                      className="rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text focus:border-jarvis-violet/50 focus:outline-none"
                    >
                      <option value="">Which project?</option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  )}
                  <input
                    value={moveNote}
                    onChange={(e) => setMoveNote(e.target.value)}
                    placeholder="Why? (optional, recorded in history)"
                    className="rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-violet/50 focus:outline-none"
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setMoving(false)}
                      className="press-scale rounded-lg border border-jarvis-border bg-jarvis-panel2/50 px-3 py-1.5 text-xs font-medium text-jarvis-muted transition hover:text-jarvis-text"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={moveSaving}
                      className="press-scale rounded-lg border border-jarvis-violet/50 bg-jarvis-violet/10 px-3 py-1.5 text-xs font-semibold text-jarvis-violet transition hover:bg-jarvis-violet/20 disabled:opacity-50"
                    >
                      {moveSaving ? "Moving..." : "Move"}
                    </button>
                  </div>
                </form>
              )}

              {selected.links.length > 0 && (
                <div className="mt-5">
                  <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-jarvis-muted">
                    <Link2 className="h-3.5 w-3.5" />
                    Linked memory
                  </div>
                  <ul className="space-y-2">
                    {selected.links.map((link, i) => (
                      <li key={i}>
                        <button
                          onClick={() => openEntry(link.entry.id)}
                          className="w-full rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2 text-left text-xs transition hover:border-jarvis-cyan/40"
                        >
                          <span className="text-jarvis-muted">{link.relation} → </span>
                          <span className="text-jarvis-text">{link.entry.title}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-5 border-t border-jarvis-border/40 pt-3">
                <button
                  onClick={toggleAudit}
                  className="flex w-full items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-jarvis-muted transition hover:text-jarvis-text"
                >
                  <History className="h-3.5 w-3.5" />
                  History
                  <ChevronDown className={clsx("h-3.5 w-3.5 transition-transform", auditOpen && "rotate-180")} />
                </button>
                {auditOpen && (
                  <div className="mt-2">
                    {auditLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-jarvis-cyan" />
                    ) : auditEntries.length === 0 ? (
                      <p className="text-xs text-jarvis-muted">No history recorded.</p>
                    ) : (
                      <ul className="space-y-1.5">
                        {auditEntries.map((entry) => (
                          <li key={entry.id} className="flex items-start gap-2 text-xs">
                            <span className="mt-0.5 shrink-0 rounded-full border border-jarvis-border/60 bg-jarvis-panel2/40 px-1.5 py-0.5 font-medium text-jarvis-text">
                              {AUDIT_ACTION_LABELS[entry.action]}
                            </span>
                            <span className="text-jarvis-muted">
                              {entry.note && `${entry.note} · `}
                              {timeAgo(entry.created_at)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {detailLoading && (
            <div className="flex flex-1 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-jarvis-cyan" />
            </div>
          )}
        </div>
    </main>
  );
}
