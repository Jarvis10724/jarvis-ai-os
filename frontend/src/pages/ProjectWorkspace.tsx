import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  CheckSquare,
  Clock,
  FileCode,
  FolderKanban,
  Image as ImageIcon,
  Layers,
  Loader2,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Brain,
} from "lucide-react";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import { useToast } from "@/context/ToastContext";
import type { ProjectOverview } from "@/types";
import { useSyncedResource } from "@/context/SyncContext";

type BucketKey =
  | "conversations"
  | "files"
  | "images"
  | "components"
  | "research"
  | "tasks"
  | "approvals"
  | "timeline"
  | "memory";

const BUCKETS: { key: BucketKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "conversations", label: "Conversations", icon: MessageSquare },
  { key: "files", label: "Files", icon: FileCode },
  { key: "images", label: "Images", icon: ImageIcon },
  { key: "components", label: "Components", icon: Layers },
  { key: "research", label: "Research", icon: Sparkles },
  { key: "tasks", label: "Tasks", icon: CheckSquare },
  { key: "approvals", label: "Approvals", icon: ShieldCheck },
  { key: "timeline", label: "Timeline", icon: Clock },
  { key: "memory", label: "Memory", icon: Brain },
];

// A single unified view of everything a Project contains — every Quick Action
// in the business rolls its output into these nine buckets. Real data from
// GET /projects/:id/overview; no mock content.
export default function ProjectWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<BucketKey>("conversations");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      setOverview(await api.getProjectOverview(id));
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to load project.", "error");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Re-read whenever this kind of state changes anywhere — any device,
  // any origin (a person, an agent, an integration). No timer here.
  useSyncedResource("projects", load);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
      </div>
    );
  }
  if (!overview) return null;

  const { project, counts } = overview;

  return (
    <div className="space-y-6">
      <ModulePageHeader
        icon={FolderKanban}
        title={project.name}
        description={project.description ?? "Shared project workspace — everything Jarvis builds for this business."}
        sampleData={false}
      />

      {/* Bucket tabs with live counts */}
      <div className="flex flex-wrap gap-2">
        {BUCKETS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={clsx(
              "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors duration-150",
              tab === key
                ? "border-jarvis-cyan/50 bg-jarvis-cyan/10 text-jarvis-cyan"
                : "border-jarvis-border bg-jarvis-panel2/30 text-jarvis-muted hover:text-jarvis-text"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
            <span className="rounded-full bg-jarvis-panel px-1.5 py-0.5 text-[10px] font-semibold">
              {counts[key]}
            </span>
          </button>
        ))}
      </div>

      <div className="hud-panel p-5">
        <BucketView tab={tab} overview={overview} onOpenAction={(a) => navigate(`/studio/${a}`)} />
      </div>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return <p className="py-8 text-center text-sm text-jarvis-muted">No {label} yet.</p>;
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-jarvis-border/50 bg-jarvis-panel2/20 px-3 py-2.5 text-sm">
      {children}
    </div>
  );
}

function BucketView({
  tab,
  overview,
  onOpenAction,
}: {
  tab: BucketKey;
  overview: ProjectOverview;
  onOpenAction: (action: string) => void;
}) {
  if (tab === "conversations") {
    const items = overview.conversations;
    if (!items.length) return <Empty label="conversations" />;
    return (
      <div className="space-y-2">
        {items.map((c) => (
          <button key={c.session_id} onClick={() => onOpenAction(c.action)} className="w-full text-left">
            <Row>
              <MessageSquare className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
              <span className="min-w-0 flex-1 truncate text-jarvis-text">{c.title}</span>
              <span className="shrink-0 text-xs text-jarvis-muted">{c.action_label}</span>
              <span className="shrink-0 text-xs text-jarvis-muted">{c.message_count} msgs</span>
            </Row>
          </button>
        ))}
      </div>
    );
  }

  if (tab === "files") {
    const items = overview.files;
    if (!items.length) return <Empty label="files" />;
    return (
      <div className="space-y-2">
        {items.map((f, i) => (
          <Row key={i}>
            <FileCode className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-jarvis-text">{f.path}</span>
            {f.language && <span className="shrink-0 text-xs text-jarvis-muted">{f.language}</span>}
            <span className="shrink-0 rounded bg-jarvis-panel px-1.5 py-0.5 text-[10px] text-jarvis-muted">
              {f.source}
            </span>
          </Row>
        ))}
      </div>
    );
  }

  if (tab === "images") {
    const items = overview.images;
    if (!items.length) return <Empty label="images" />;
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {items.map((im, i) => (
          <div key={im.id ?? i} className="overflow-hidden rounded-lg border border-jarvis-border/50 bg-jarvis-panel2/20">
            {im.data_url ? (
              <img src={im.data_url} alt={im.name ?? "image"} className="aspect-square w-full object-cover" />
            ) : (
              <div className="flex aspect-square items-center justify-center">
                <ImageIcon className="h-6 w-6 text-jarvis-muted" />
              </div>
            )}
            <p className="truncate px-2 py-1.5 text-xs text-jarvis-muted">{im.name ?? "Untitled"}</p>
          </div>
        ))}
      </div>
    );
  }

  if (tab === "components") {
    const items = overview.components;
    if (!items.length) return <Empty label="components" />;
    return (
      <div className="space-y-2">
        {items.map((c, i) => (
          <Row key={i}>
            <Layers className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-jarvis-text">{c.path}</span>
            {c.description && <span className="shrink-0 truncate text-xs text-jarvis-muted">{c.description}</span>}
          </Row>
        ))}
      </div>
    );
  }

  if (tab === "research") {
    const items = overview.research;
    if (!items.length) return <Empty label="research" />;
    return (
      <div className="space-y-2">
        {items.map((r, i) => (
          <button key={i} onClick={() => onOpenAction("deep_research")} className="w-full text-left">
            <Row>
              <Sparkles className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
              <span className="min-w-0 flex-1 truncate text-jarvis-text">{r.title}</span>
              <span className="shrink-0 text-xs text-jarvis-muted">
                {r.source_count} sources · {r.citation_count} cites{r.has_report ? " · report" : ""}
              </span>
            </Row>
          </button>
        ))}
      </div>
    );
  }

  if (tab === "tasks") {
    const items = overview.tasks;
    if (!items.length) return <Empty label="tasks" />;
    return (
      <div className="space-y-2">
        {items.map((t) => (
          <Row key={t.id}>
            <CheckSquare className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
            <span className="min-w-0 flex-1 truncate text-jarvis-text">{t.title}</span>
            <span className="shrink-0 rounded bg-jarvis-panel px-1.5 py-0.5 text-[10px] uppercase text-jarvis-muted">
              {t.status}
            </span>
          </Row>
        ))}
      </div>
    );
  }

  if (tab === "approvals") {
    const items = overview.approvals;
    if (!items.length) return <Empty label="approvals" />;
    return (
      <div className="space-y-2">
        {items.map((a) => (
          <Row key={a.id}>
            <ShieldCheck className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
            <span className="min-w-0 flex-1 truncate text-jarvis-text">
              {a.capability_name} · {a.action_type}
            </span>
            <span className="shrink-0 rounded bg-jarvis-panel px-1.5 py-0.5 text-[10px] uppercase text-jarvis-muted">
              {a.status}
            </span>
          </Row>
        ))}
      </div>
    );
  }

  if (tab === "memory") {
    const items = overview.memory;
    if (!items.length) return <Empty label="memory" />;
    return (
      <div className="space-y-2">
        {items.map((m) => (
          <Row key={m.id}>
            <Brain className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
            <span className="min-w-0 flex-1 truncate text-jarvis-text">{m.title}</span>
            <span className="shrink-0 text-xs text-jarvis-muted">{m.kind}</span>
          </Row>
        ))}
      </div>
    );
  }

  // timeline
  const items = overview.timeline;
  if (!items.length) return <Empty label="timeline events" />;
  return (
    <div className="space-y-2">
      {items.map((e) => (
        <Row key={e.id}>
          <Clock className="h-4 w-4 shrink-0 text-jarvis-cyan/80" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-jarvis-text">{e.title}</p>
            {e.detail && <p className="truncate text-xs text-jarvis-muted">{e.detail}</p>}
          </div>
          <span className="shrink-0 text-xs text-jarvis-muted">
            {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
          </span>
        </Row>
      ))}
    </div>
  );
}
