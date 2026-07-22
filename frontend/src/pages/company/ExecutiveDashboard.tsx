import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  BrainCircuit,
  CalendarClock,
  ChevronRight,
  Gauge,
  Mail,
  MessageSquare,
  Package,
  RefreshCw,
  Rocket,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { api } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import { useCompany } from "@/context/CompanyContext";
import { useWorkspace } from "@/hooks/useWorkspace";
import type {
  AgentRun,
  ApprovalRequestView,
  BrandBrainSummary,
  CalendarEventView,
  CompanyTask,
  MemoryEntry,
  ProjectSummary,
} from "@/types";

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

interface DashData {
  projects: ProjectSummary[];
  tasks: CompanyTask[];
  approvals: ApprovalRequestView[];
  runs: AgentRun[];
  conversations: MemoryEntry[];
  gmail: { connected: boolean; unread: number };
  calendar: { connected: boolean; next: CalendarEventView | null; count: number };
  brain: BrandBrainSummary | null;
}

const EMPTY: DashData = {
  projects: [],
  tasks: [],
  approvals: [],
  runs: [],
  conversations: [],
  gmail: { connected: false, unread: 0 },
  calendar: { connected: false, next: null, count: 0 },
  brain: null,
};

/**
 * Executive Dashboard (Phase 3) — a single per-workspace operating view that
 * aggregates the workspace's live state: projects, task progress, AI activity,
 * recent conversations, approvals, Gmail/Calendar summaries, Brand Brain, and a
 * derived health read. Additive and read-only — it reuses existing APIs and
 * every card taps through to the module that owns it. Mobile-first: one column
 * on phones, widening to a grid on larger screens.
 */
export default function ExecutiveDashboardPage() {
  const { activeCompany, activeCompanyId } = useCompany();
  const workspace = useWorkspace();
  const navigate = useNavigate();
  const [data, setData] = useState<DashData>(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!activeCompanyId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const cid = activeCompanyId;
    const next = { ...EMPTY };
    await Promise.allSettled([
      api.listProjects(cid).then((p) => (next.projects = p)),
      api.listCompanyTasks(cid).then((t) => (next.tasks = t)),
      api.listApprovals({ companyId: cid, status: "pending" }).then((a) => (next.approvals = a)),
      api.listAgentRuns({ companyId: cid }).then((r) => (next.runs = r)),
      api.searchMemory({ companyId: cid, kind: "conversation", limit: 6 }).then((m) => (next.conversations = m)),
      api
        .listGmailMessages({ companyId: cid, unreadOnly: true, maxResults: 50 })
        .then((g) => (next.gmail = { connected: true, unread: g.length }))
        .catch(() => (next.gmail = { connected: false, unread: 0 })),
      api
        .listCalendarEvents({ companyId: cid, upcomingOnly: true, maxResults: 5 })
        .then((e) => (next.calendar = { connected: true, next: e[0] ?? null, count: e.length }))
        .catch(() => (next.calendar = { connected: false, next: null, count: 0 })),
      api.getBrandBrain(cid).then((b) => (next.brain = b)).catch(() => (next.brain = null)),
    ]);
    setData(next);
    setLoading(false);
  }, [activeCompanyId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!activeCompanyId) {
    return (
      <main className="flex h-full flex-1 items-center justify-center p-6 text-center text-sm text-jarvis-muted">
        Select a workspace to view its Executive Dashboard.
      </main>
    );
  }

  const tasksDone = data.tasks.filter((t) => t.status === "done").length;
  const taskPct = data.tasks.length ? Math.round((tasksDone / data.tasks.length) * 100) : 0;
  const activeProjects = data.projects.filter((p) => p.status !== "done");
  const runningAgents = data.runs.filter((r) => r.status === "running").length;

  // Workspace health — derived from real attention signals, not fabricated.
  const attention =
    data.approvals.length + (data.gmail.unread > 0 ? 1 : 0) + (data.brain && !data.brain.exists ? 1 : 0);
  const healthy = attention === 0;

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <ModulePageHeader
        icon={Gauge}
        title="Executive Dashboard"
        description={`Everything happening in ${activeCompany?.name ?? "this workspace"} — projects, work, AI activity, and health, in one view.`}
        sampleData={false}
        actions={
          <button
            onClick={load}
            className="press-scale flex items-center gap-2 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
          >
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Refresh
          </button>
        }
      />

      {/* Workspace health hero */}
      <div
        className="hud-panel hud-corner flex items-center gap-4 p-4"
        style={{ borderColor: "var(--ws-accent-soft)" }}
      >
        <span
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl font-display text-base font-bold"
          style={{ backgroundColor: "var(--ws-accent-faint)", color: "var(--ws-accent)" }}
        >
          {workspace.monogram}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-jarvis-text">{activeCompany?.name}</p>
          <p className="text-xs text-jarvis-muted">
            {workspace.role} ·{" "}
            <span className={healthy ? "text-jarvis-emerald" : "text-jarvis-amber"}>
              {healthy ? "All clear" : `${attention} item${attention === 1 ? "" : "s"} need attention`}
            </span>
          </p>
        </div>
        <span
          className={`h-3 w-3 shrink-0 animate-pulseGlow rounded-full ${healthy ? "bg-jarvis-emerald" : "bg-jarvis-amber"}`}
        />
      </div>

      {loading && <div className="skeleton h-40 rounded-2xl" />}

      {!loading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Card icon={Rocket} tone="emerald" title="Active projects" metric={activeProjects.length} onClick={() => navigate("/company/projects")}>
            {activeProjects.slice(0, 3).map((p) => (
              <Row key={p.id} label={p.name} sub={p.status.replace("_", " ")} onClick={() => navigate(`/projects/${p.id}`)} />
            ))}
            {activeProjects.length === 0 && <Empty label="No active projects" />}
          </Card>

          <Card icon={Activity} tone="cyan" title="Task progress" metric={`${taskPct}%`} onClick={() => navigate("/company/projects")}>
            <div className="mb-1 h-2 w-full overflow-hidden rounded-full bg-jarvis-border/50">
              <div className="h-full rounded-full" style={{ width: `${taskPct}%`, backgroundColor: "var(--ws-accent)" }} />
            </div>
            <p className="text-[11px] text-jarvis-muted">
              {tasksDone}/{data.tasks.length} done · {data.tasks.filter((t) => t.status === "in_progress").length} in progress
            </p>
          </Card>

          <Card icon={ShieldCheck} tone="amber" title="Pending approvals" metric={data.approvals.length} onClick={() => navigate("/approvals")}>
            {data.approvals.slice(0, 3).map((a) => (
              <Row key={a.id} label={`${a.capability_name} · ${a.action_type}`.replace(/_/g, " ")} sub={timeAgo(a.created_at)} onClick={() => navigate("/approvals")} />
            ))}
            {data.approvals.length === 0 && <Empty label="All clear" />}
          </Card>

          <Card icon={BrainCircuit} tone="violet" title="AI activity" metric={runningAgents || data.runs.length} onClick={() => navigate("/automation")}>
            {data.runs.slice(0, 3).map((r) => (
              <Row key={r.id} label={r.agent_label} sub={`${r.status} · ${timeAgo(r.created_at)}`} onClick={() => navigate("/automation")} />
            ))}
            {data.runs.length === 0 && <Empty label="No agent runs yet" />}
          </Card>

          <Card icon={MessageSquare} tone="blue" title="Recent conversations" metric={data.conversations.length} onClick={() => navigate(`/memory?company=${activeCompanyId}`)}>
            {data.conversations.slice(0, 3).map((c) => (
              <Row key={c.id} label={c.title} sub={timeAgo(c.created_at)} onClick={() => navigate(`/memory?company=${activeCompanyId}`)} />
            ))}
            {data.conversations.length === 0 && <Empty label="No conversations yet" />}
          </Card>

          <Card icon={Package} tone="cyan" title="Brand Brain" metric={data.brain?.exists ? (data.brain.product_count ?? 0) : "—"} onClick={() => navigate("/company/brand-brain")}>
            {data.brain?.exists ? (
              <p className="text-[11px] text-jarvis-muted">
                {data.brain.product_count} products · {data.brain.collection_count} collections
                <br />
                {data.brain.store_name} · synced {timeAgo(data.brain.last_synced_at)}
              </p>
            ) : (
              <Empty label="Not synced yet" />
            )}
          </Card>

          <Card icon={Mail} tone="blue" title="Gmail" metric={data.gmail.connected ? data.gmail.unread : "—"} onClick={() => navigate(`/integrations?company=${activeCompanyId}`)}>
            <p className="text-[11px] text-jarvis-muted">
              {data.gmail.connected ? `${data.gmail.unread} unread` : "Not connected"}
            </p>
          </Card>

          <Card icon={CalendarClock} tone="cyan" title="Calendar" metric={data.calendar.connected ? data.calendar.count : "—"} onClick={() => navigate(`/integrations?company=${activeCompanyId}`)}>
            <p className="truncate text-[11px] text-jarvis-muted">
              {data.calendar.connected ? data.calendar.next?.summary ?? "No upcoming events" : "Not connected"}
            </p>
          </Card>
        </div>
      )}
    </main>
  );
}

const TONE: Record<string, string> = {
  cyan: "text-jarvis-cyan",
  blue: "text-jarvis-blue",
  violet: "text-jarvis-violet",
  amber: "text-jarvis-amber",
  emerald: "text-jarvis-emerald",
};

function Card({
  icon: Icon,
  tone,
  title,
  metric,
  onClick,
  children,
}: {
  icon: LucideIcon;
  tone: keyof typeof TONE | string;
  title: string;
  metric: string | number;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="hud-panel hud-corner group flex flex-col gap-2 p-4 text-left transition-colors hover:border-[color:var(--ws-accent-soft)]"
    >
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${TONE[tone] ?? "text-jarvis-cyan"}`} />
        <span className="text-[11px] font-semibold uppercase tracking-widest text-jarvis-faint">{title}</span>
        <span className="ml-auto text-lg font-bold text-jarvis-text">{metric}</span>
        <ChevronRight className="h-4 w-4 text-jarvis-faint transition-colors group-hover:text-jarvis-text" />
      </div>
      <div className="space-y-1">{children}</div>
    </button>
  );
}

function Row({ label, sub, onClick }: { label: string; sub?: string; onClick?: () => void }) {
  return (
    <div
      onClick={
        onClick
          ? (e) => {
              e.stopPropagation();
              onClick();
            }
          : undefined
      }
      className="flex items-center justify-between gap-2 rounded-lg px-1 py-0.5 hover:bg-jarvis-panel2/40"
    >
      <span className="min-w-0 truncate text-xs text-jarvis-text">{label}</span>
      {sub && <span className="shrink-0 text-[10px] capitalize text-jarvis-muted">{sub}</span>}
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return <p className="text-[11px] text-jarvis-muted">{label}</p>;
}
