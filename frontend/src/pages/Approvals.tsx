import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ClipboardList,
  HeartPulse,
  History,
  Loader2,
  Pencil,
  RotateCcw,
  ShieldCheck,
  Undo2,
  X,
} from "lucide-react";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill from "@/components/StatusPill";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import type {
  ApprovalDecisionResult,
  ApprovalPlan,
  ApprovalQueue,
  ApprovalRequestView,
  CapabilityAuditEntry,
  CapabilityView,
} from "@/types";

const HEALTH_TONE: Record<CapabilityView["health_status"], "neutral" | "success" | "danger" | "accent"> = {
  unknown: "neutral",
  ok: "success",
  error: "danger",
  disconnected: "accent",
};

type DecideOpts = { payload?: Record<string, unknown>; note?: string };
type DecideFn = (request: ApprovalRequestView, approve: boolean, opts?: DecideOpts) => void;

/**
 * The Approval Center — the gate every real-world action passes through.
 *
 * Nothing here is a rubber stamp: each request arrives with a brief (what it
 * is, why it was proposed, what will happen, what could go wrong, and whether
 * it can be undone), so the decision is made on facts rather than raw JSON.
 * Approve, reject, or edit-then-approve; decide one step or a whole execution
 * plan at once.
 *
 * The queue is served from the database, so it is identical after a refresh, a
 * restart, or on another device. Approving runs the action immediately through
 * its registered executor — and for a plan, runs the steps in sequence.
 */
export default function ApprovalsPage() {
  const { activeCompany, activeCompanyId } = useCompany();
  const toast = useToast();
  const navigate = useNavigate();
  const [queue, setQueue] = useState<ApprovalQueue | null>(null);
  const [history, setHistory] = useState<ApprovalRequestView[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const [capabilities, setCapabilities] = useState<CapabilityView[]>([]);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(true);
  const [busyCapability, setBusyCapability] = useState<string | null>(null);

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!opts?.silent) setLoading(true);
      try {
        const [q, h] = await Promise.all([
          api.approvalQueue(activeCompanyId),
          api.approvalHistory(activeCompanyId).catch(() => []),
        ]);
        setQueue(q);
        setHistory(h);
      } catch (err) {
        // A silent background refresh must not nag: the visible state is still
        // the last good one, and the next tick retries.
        if (!opts?.silent) {
          toast.push(err instanceof ApiError ? err.message : "Couldn't load the approval queue.", "error");
        }
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [activeCompanyId, toast],
  );

  const loadCapabilities = useCallback(async () => {
    setCapabilitiesLoading(true);
    try {
      setCapabilities(await api.listCapabilities(activeCompanyId ?? undefined));
    } catch {
      setCapabilities([]);
    } finally {
      setCapabilitiesLoading(false);
    }
  }, [activeCompanyId]);

  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    loadCapabilities();
  }, [loadCapabilities]);

  /* Keep the phone and the desktop looking at the same queue.
   *
   * The queue itself already lives in the backend database — nothing here is
   * client-side state — so both devices are reading one source of truth. What
   * was missing is that a device only read it on mount: a proposal raised on
   * the phone sat invisible on the desktop until someone refreshed.
   *
   * Short polling, not a socket: this app has no WebSocket transport, and an
   * approval queue changes a few times an hour, not a few times a second. A
   * refresh on focus covers the common case (pick the phone up, it's current);
   * the interval covers a screen left open on the desk. Skipped while a
   * decision is in flight so a poll can't clobber the row being decided. */
  const busyRef = useRef<string | null>(null);
  busyRef.current = busy;
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState !== "visible" || busyRef.current) return;
      load({ silent: true });
    };
    const timer = window.setInterval(refresh, 8000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [load]);

  /** Report what actually happened — carried out, consented, failed, re-planned. */
  function reportOutcome(result: ApprovalDecisionResult, fallback: string) {
    if (result.execution_error) {
      toast.push(`Approved, but it couldn't be carried out: ${result.execution_error}`, "error");
    } else if (result.replan?.replanned) {
      toast.push(`Rejected. Jarvis re-planned around it: ${result.replan.new_steps.join(", ")}`, "info");
    } else if (result.replan && !result.replan.replanned) {
      toast.push("Rejected. No alternative path was found, so the plan stopped here.", "info");
    } else if (result.execution_note) {
      toast.push(result.execution_note, "info");
    } else {
      toast.push(fallback, "success");
    }
  }

  const decide: DecideFn = async (request, approve, opts) => {
    // A second tap while the first is in flight must not send a second
    // decision — on a phone that's one approval producing two store writes.
    // The buttons are disabled too; this is the guard that doesn't depend on
    // a re-render having happened yet.
    if (busyRef.current) return;
    busyRef.current = request.id;
    setBusy(request.id);
    try {
      const result = approve
        ? await api.approveRequest(request.id, opts?.note, opts?.payload)
        : await api.rejectRequest(request.id, opts?.note);
      reportOutcome(result, approve ? "Approved and carried out." : "Rejected.");
      await load();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't record that decision.", "error");
    } finally {
      setBusy(null);
    }
  };

  async function decidePlan(plan: ApprovalPlan, approve: boolean) {
    setBusy(plan.group_id);
    try {
      const result = approve ? await api.approvePlan(plan.group_id) : await api.rejectPlan(plan.group_id);
      if (result.stopped_at) {
        toast.push("Stopped partway: a step failed, so the rest of the plan was left pending.", "error");
      } else {
        toast.push(
          approve
            ? `Approved ${result.decided} step${result.decided === 1 ? "" : "s"} and ran them in order.`
            : `Rejected ${result.decided} step${result.decided === 1 ? "" : "s"}.`,
          approve ? "success" : "info"
        );
      }
      await load();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Couldn't decide that plan.", "error");
    } finally {
      setBusy(null);
    }
  }

  async function toggleCapability(capability: CapabilityView) {
    setBusyCapability(capability.name);
    try {
      await api.updateCapabilityConfig(capability.name, {
        enabled: !capability.enabled,
        company_id: activeCompanyId ?? null,
      });
      await loadCapabilities();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to update capability.", "error");
    } finally {
      setBusyCapability(null);
    }
  }

  async function checkHealth(capability: CapabilityView) {
    setBusyCapability(capability.name);
    try {
      const updated = await api.runCapabilityHealthCheck(capability.name, activeCompanyId ?? undefined);
      setCapabilities((prev) => prev.map((c) => (c.name === updated.name ? updated : c)));
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Health check failed.", "error");
    } finally {
      setBusyCapability(null);
    }
  }

  const pendingStandalone = queue?.standalone.filter((r) => r.status === "pending") ?? [];

  return (
    <main className="h-full min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
      <ModulePageHeader
        icon={ShieldCheck}
        title="Approval Center"
        description={`Every action with real-world consequences in ${activeCompany?.name ?? "this workspace"} waits here. Nothing runs until you say so — and what you approve is carried out immediately.`}
        sampleData={false}
      />

      {loading && !queue ? (
        <div className="hud-panel hud-corner space-y-3 p-4">
          <div className="skeleton h-4 w-2/3 rounded" />
          <div className="skeleton h-3 w-full rounded" />
        </div>
      ) : (
        <>
          {queue?.pending_count === 0 && (
            <div className="hud-panel hud-corner flex items-center gap-3 p-4 text-sm text-jarvis-muted">
              <Check className="h-4 w-4 shrink-0 text-jarvis-emerald" />
              Nothing is waiting for your approval.
            </div>
          )}

          {queue?.plans.map((plan) => (
            <PlanCard
              key={plan.group_id}
              plan={plan}
              busy={busy}
              onDecideStep={decide}
              onDecidePlan={decidePlan}
              onOpenPlan={() => navigate(`/company/work-queue?run=${plan.group_id}`)}
            />
          ))}

          {pendingStandalone.map((request) => (
            <RequestCard key={request.id} request={request} busy={busy} onDecide={decide} />
          ))}

          {/* The record: what has already been decided, and why. */}
          <section className="hud-panel hud-corner p-4">
            <button
              onClick={() => setShowHistory((v) => !v)}
              className="flex w-full items-center gap-2 text-left text-xs font-semibold uppercase tracking-widest text-jarvis-faint"
            >
              <History className="h-3.5 w-3.5" />
              Decision history ({history.length})
              <ChevronDown className={clsx("ml-auto h-4 w-4 transition-transform", showHistory && "rotate-180")} />
            </button>
            {showHistory && (
              <ul className="mt-3 space-y-2">
                {history.length === 0 && <li className="text-sm text-jarvis-muted">Nothing decided yet.</li>}
                {history.map((h) => (
                  <li key={h.id} className="flex items-start gap-2 text-sm">
                    <StatusDot status={h.status} />
                    <div className="min-w-0 flex-1">
                      <p className="text-jarvis-text">{h.summary}</p>
                      <p className="text-[11px] text-jarvis-muted">
                        {h.status}
                        {h.decided_at ? ` · ${new Date(h.decided_at).toLocaleString()}` : ""}
                        {h.note ? ` · “${h.note}”` : ""}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {/* Which capabilities are allowed to propose anything at all. */}
      <ModulePageHeader
        icon={HeartPulse}
        title="Capabilities"
        description="Enable/disable and check connection health per capability. A disabled capability can't even propose an action."
        sampleData={false}
      />
      <div className="hud-panel hud-corner">
        <ul className="divide-y divide-jarvis-border/40">
          {capabilitiesLoading && (
            <li className="flex justify-center px-5 py-10">
              <Loader2 className="h-5 w-5 animate-spin text-jarvis-cyan" />
            </li>
          )}
          {!capabilitiesLoading &&
            capabilities.map((cap) => (
              <li key={cap.name} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium capitalize text-jarvis-text">{cap.name.replace("_", " ")}</p>
                  <p className="text-xs text-jarvis-muted">{cap.description}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusPill label={cap.health_status} tone={HEALTH_TONE[cap.health_status]} />
                  <button
                    onClick={() => checkHealth(cap)}
                    disabled={busyCapability === cap.name}
                    className="press-scale rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-1.5 text-xs font-medium text-jarvis-muted transition hover:text-jarvis-text disabled:opacity-50"
                  >
                    Check health
                  </button>
                  <button
                    onClick={() => toggleCapability(cap)}
                    disabled={busyCapability === cap.name}
                    className={clsx(
                      "press-scale rounded-xl border px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50",
                      cap.enabled
                        ? "border-jarvis-emerald/50 bg-jarvis-emerald/10 text-jarvis-emerald hover:bg-jarvis-emerald/20"
                        : "border-jarvis-border bg-jarvis-panel2/50 text-jarvis-muted hover:text-jarvis-text"
                    )}
                  >
                    {cap.enabled ? "Enabled" : "Disabled"}
                  </button>
                </div>
              </li>
            ))}
        </ul>
      </div>
    </main>
  );
}

function StatusDot({ status }: { status: string }) {
  const tone =
    status === "executed" || status === "approved"
      ? "bg-jarvis-emerald"
      : status === "rejected"
        ? "bg-jarvis-rose"
        : "bg-jarvis-amber";
  return <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", tone)} />;
}

/** An execution plan: many steps, decidable together or one at a time. */
function PlanCard({
  plan,
  busy,
  onDecideStep,
  onDecidePlan,
  onOpenPlan,
}: {
  plan: ApprovalPlan;
  busy: string | null;
  onDecideStep: DecideFn;
  onDecidePlan: (plan: ApprovalPlan, approve: boolean) => void;
  onOpenPlan: () => void;
}) {
  const pending = plan.steps.filter((s) => s.status === "pending");
  if (pending.length === 0) return null;
  const working = busy === plan.group_id;

  return (
    <section className="hud-panel hud-corner space-y-3 p-4">
      <div className="flex items-start gap-2">
        <ClipboardList className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--ws-accent)" }} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-jarvis-text">{plan.label}</p>
          <button onClick={onOpenPlan} className="text-[11px] text-jarvis-muted underline-offset-2 hover:underline">
            {pending.length} step{pending.length === 1 ? "" : "s"} awaiting approval · open the plan →
          </button>
        </div>
      </div>

      {/* Whole-plan decision: approving runs the steps in order. */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onDecidePlan(plan, true)}
          disabled={working}
          className="press-scale flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-jarvis-emerald/40 bg-jarvis-emerald/10 px-3 py-2 text-xs font-semibold text-jarvis-emerald transition hover:bg-jarvis-emerald/20 disabled:opacity-40"
        >
          {working ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          Approve all {pending.length} in order
        </button>
        <button
          onClick={() => onDecidePlan(plan, false)}
          disabled={working}
          className="press-scale flex items-center justify-center gap-1.5 rounded-xl border border-jarvis-border px-3 py-2 text-xs font-semibold text-jarvis-muted transition hover:bg-jarvis-panel2/60 disabled:opacity-40"
        >
          <X className="h-3.5 w-3.5" /> Reject all
        </button>
      </div>

      <div className="space-y-2 border-t border-jarvis-border/40 pt-2">
        {pending.map((step, i) => (
          <RequestCard key={step.id} request={step} busy={busy} onDecide={onDecideStep} stepNumber={i + 1} nested />
        ))}
      </div>
    </section>
  );
}

type PreviewField = { field: string; before: unknown; after: unknown };
type StoreChangePreview = {
  resolved?: boolean;
  product?: string;
  field?: string;
  before?: unknown;
  after?: unknown;
  fields?: PreviewField[];
  warnings?: string[];
};

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/**
 * Current value against proposed value, for a storefront change.
 *
 * This is what the approval is actually FOR, so it renders as a side-by-side
 * block rather than being buried in the payload JSON — legible at 375px, where
 * most of these get decided. An unresolved preview says so instead of showing
 * a blank "before" that would read as "currently empty".
 */
function ChangePreview({ payload }: { payload: Record<string, unknown> | null | undefined }) {
  const preview = payload?._preview as StoreChangePreview | undefined;
  if (!preview) return null;

  if (!preview.resolved) {
    return (
      <p className="mt-2.5 rounded-xl border border-jarvis-amber/40 bg-jarvis-amber/10 p-2.5 text-xs text-jarvis-amber">
        Couldn't match {preview.product ? `"${preview.product}"` : "this item"} to a product in the synced
        catalog, so the current value is unknown. Re-sync the store before approving.
      </p>
    );
  }

  const rows: PreviewField[] =
    preview.fields && preview.fields.length > 0
      ? preview.fields
      : preview.field
        ? [{ field: preview.field, before: preview.before, after: preview.after }]
        : [];
  if (rows.length === 0) return null;

  return (
    <div className="mt-2.5 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/30 p-3">
      {preview.product && (
        <p className="mb-2 truncate text-xs font-semibold text-jarvis-text">{preview.product}</p>
      )}
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.field}>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-jarvis-faint">
              {row.field.replace(/_/g, " ")}
            </p>
            <div className="grid grid-cols-2 gap-2">
              <div className="min-w-0 rounded-lg bg-jarvis-panel3/40 px-2 py-1.5">
                <p className="text-[10px] uppercase tracking-wide text-jarvis-faint">Current</p>
                <p className="break-words font-data text-xs text-jarvis-muted line-through decoration-jarvis-rose/50">
                  {show(row.before)}
                </p>
              </div>
              <div className="min-w-0 rounded-lg border border-jarvis-emerald/30 bg-jarvis-emerald/10 px-2 py-1.5">
                <p className="text-[10px] uppercase tracking-wide text-jarvis-faint">Proposed</p>
                <p className="break-words font-data text-xs font-semibold text-jarvis-emerald">
                  {show(row.after)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
      {(preview.warnings ?? []).map((w, i) => (
        <p key={i} className="mt-2 text-[11px] text-jarvis-amber">
          {w}
        </p>
      ))}
    </div>
  );
}

/** One request, with everything a human needs in order to decide it. */
function RequestCard({
  request,
  busy,
  onDecide,
  stepNumber,
  nested = false,
}: {
  request: ApprovalRequestView;
  busy: string | null;
  onDecide: DecideFn;
  stepNumber?: number;
  nested?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [expanded, setExpanded] = useState(!nested);
  const [audit, setAudit] = useState<CapabilityAuditEntry[] | null>(null);
  const working = busy === request.id;

  function startEditing() {
    setDraft(JSON.stringify(request.payload ?? {}, null, 2));
    setInvalid(false);
    setEditing(true);
    setExpanded(true);
  }

  function approveEdited() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(draft);
    } catch {
      setInvalid(true);
      return;
    }
    setEditing(false);
    onDecide(request, true, { payload: parsed, note: "Edited before approval." });
  }

  async function toggleAudit() {
    if (audit) return setAudit(null);
    try {
      setAudit(await api.approvalAudit(request.id));
    } catch {
      setAudit([]);
    }
  }

  return (
    <article
      className={nested ? "rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 p-3" : "hud-panel hud-corner p-4"}
    >
      <div className="flex items-start gap-2">
        {stepNumber !== undefined && (
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-jarvis-panel3/50 text-[10px] font-bold text-jarvis-muted">
            {stepNumber}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-jarvis-text">{request.summary}</p>
          <p className="mt-0.5 text-[11px] uppercase tracking-wide text-jarvis-faint">
            {request.capability_name} · {request.action_type}
          </p>
        </div>
        {nested && (
          <button
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? "Hide details" : "Show details"}
            className="press-scale shrink-0 rounded-lg p-1 text-jarvis-muted hover:text-jarvis-text"
          >
            <ChevronDown className={clsx("h-4 w-4 transition-transform", expanded && "rotate-180")} />
          </button>
        )}
      </div>

      {/* The diff, always visible — collapsed or not. It is the decision. */}
      <ChangePreview payload={request.payload} />

      {expanded && (
        <div className="mt-2.5 space-y-2.5 text-xs">
          {request.reason && <Field label="Why" value={request.reason} />}
          <Field label="Expected outcome" value={request.expected_outcome} />

          {request.risks.length > 0 && (
            <div>
              <p className="mb-1 flex items-center gap-1 font-semibold uppercase tracking-wide text-jarvis-amber">
                <AlertTriangle className="h-3 w-3" /> Risks
              </p>
              <ul className="space-y-0.5">
                {request.risks.map((risk, i) => (
                  <li key={i} className="text-jarvis-muted">
                    · {risk}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <p className="mb-1 flex items-center gap-1 font-semibold uppercase tracking-wide text-jarvis-faint">
              <Undo2 className="h-3 w-3" /> If this turns out wrong
            </p>
            <p className="text-jarvis-muted">{request.undo_plan}</p>
          </div>

          {/* What will actually run — editable before approving. */}
          {editing ? (
            <div>
              <p className="mb-1 font-semibold uppercase tracking-wide text-jarvis-faint">Edit before approving</p>
              <textarea
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  setInvalid(false);
                }}
                rows={6}
                spellCheck={false}
                className={clsx(
                  "w-full resize-y rounded-lg border bg-jarvis-panel2/50 px-2 py-1.5 font-data text-[11px] text-jarvis-text focus:outline-none",
                  invalid ? "border-jarvis-rose" : "border-jarvis-border"
                )}
              />
              {invalid && <p className="mt-1 text-jarvis-rose">That isn't valid JSON — fix it before approving.</p>}
            </div>
          ) : (
            request.payload && (
              <details className="text-jarvis-muted">
                <summary className="cursor-pointer font-semibold uppercase tracking-wide text-jarvis-faint">
                  Exactly what will run
                </summary>
                <pre className="mt-1 overflow-x-auto rounded-lg bg-jarvis-panel2/40 p-2 font-data text-[10px]">
                  {JSON.stringify(request.payload, null, 2)}
                </pre>
              </details>
            )
          )}

          <button
            onClick={toggleAudit}
            className="text-[11px] font-medium text-jarvis-muted underline-offset-2 hover:underline"
          >
            {audit ? "Hide trail" : "Show trail"}
          </button>
          {audit && (
            <ul className="space-y-1 border-l border-jarvis-border/50 pl-2">
              {audit.length === 0 && <li className="text-jarvis-muted">No entries yet.</li>}
              {audit.map((row) => (
                <li key={row.id} className="text-[11px] text-jarvis-muted">
                  <span className="font-semibold text-jarvis-text">{row.action}</span>
                  {row.created_at ? ` · ${new Date(row.created_at).toLocaleString()}` : ""}
                  {row.note ? ` · ${row.note}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {editing ? (
          <>
            <button
              onClick={approveEdited}
              disabled={working}
              className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-emerald/40 bg-jarvis-emerald/10 px-3 py-2 text-xs font-semibold text-jarvis-emerald transition hover:bg-jarvis-emerald/20 disabled:opacity-40"
            >
              <Check className="h-3.5 w-3.5" /> Approve edited
            </button>
            <button
              onClick={() => setEditing(false)}
              className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-border px-3 py-2 text-xs font-semibold text-jarvis-muted transition hover:bg-jarvis-panel2/60"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Cancel
            </button>
          </>
        ) : (
          <>
            {/* Full-width and 44px tall on a phone, inline on a desktop. These
                commit real changes to a live store — they should be hard to
                mis-tap and obviously busy once tapped. */}
            <button
              onClick={() => onDecide(request, true)}
              disabled={working}
              className="press-scale flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-xl border border-jarvis-emerald/40 bg-jarvis-emerald/10 px-3 py-2 text-sm font-semibold text-jarvis-emerald transition hover:bg-jarvis-emerald/20 disabled:opacity-40 sm:min-h-0 sm:flex-none sm:text-xs"
            >
              {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              {working ? "Working…" : "Approve"}
            </button>
            <button
              onClick={() => onDecide(request, false)}
              disabled={working}
              className="press-scale flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-xl border border-jarvis-border px-3 py-2 text-sm font-semibold text-jarvis-muted transition hover:bg-jarvis-panel2/60 disabled:opacity-40 sm:min-h-0 sm:flex-none sm:text-xs"
            >
              <X className="h-4 w-4" /> Reject
            </button>
            <button
              onClick={startEditing}
              disabled={working}
              className="press-scale flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-jarvis-border px-3 py-2 text-sm font-semibold text-jarvis-muted transition hover:bg-jarvis-panel2/60 disabled:opacity-40 sm:min-h-0 sm:text-xs"
            >
              <Pencil className="h-4 w-4" /> Edit
            </button>
          </>
        )}
      </div>
    </article>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-0.5 font-semibold uppercase tracking-wide text-jarvis-faint">{label}</p>
      <p className="text-jarvis-muted">{value}</p>
    </div>
  );
}
