import { useCallback, useEffect, useState } from "react";
import { Check, HeartPulse, Loader2, ShieldCheck, X } from "lucide-react";
import clsx from "clsx";

import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill from "@/components/StatusPill";
import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import type { ApprovalRequestView, ApprovalStatus, CapabilityView } from "@/types";

const STATUS_TONE: Record<ApprovalStatus, "info" | "success" | "danger" | "neutral"> = {
  pending: "info",
  approved: "success",
  rejected: "danger",
  expired: "neutral",
  executed: "success",
};

const HEALTH_TONE: Record<CapabilityView["health_status"], "neutral" | "success" | "danger" | "accent"> = {
  unknown: "neutral",
  ok: "success",
  error: "danger",
  disconnected: "accent",
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

export default function ApprovalsPage() {
  const { companies } = useCompany();
  const toast = useToast();

  const [companyFilter, setCompanyFilter] = useState<string>("any");
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | "">("pending");
  const [approvals, setApprovals] = useState<ApprovalRequestView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const [capabilities, setCapabilities] = useState<CapabilityView[]>([]);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(true);
  const [busyCapability, setBusyCapability] = useState<string | null>(null);

  const capabilityCompanyId = companyFilter === "any" ? undefined : companyFilter;

  const loadApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listApprovals({
        companyId: companyFilter as "any" | string,
        status: statusFilter || undefined,
      });
      setApprovals(list);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load approvals.");
    } finally {
      setLoading(false);
    }
  }, [companyFilter, statusFilter]);

  const loadCapabilities = useCallback(async () => {
    setCapabilitiesLoading(true);
    try {
      const list = await api.listCapabilities(capabilityCompanyId);
      setCapabilities(list);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to load capabilities.", "error");
    } finally {
      setCapabilitiesLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capabilityCompanyId]);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  useEffect(() => {
    loadCapabilities();
  }, [loadCapabilities]);

  async function decide(id: string, action: "approve" | "reject") {
    setDecidingId(id);
    try {
      if (action === "approve") await api.approveRequest(id);
      else await api.rejectRequest(id);
      toast.push(action === "approve" ? "Approved." : "Rejected.", "success");
      await loadApprovals();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : `Failed to ${action}.`, "error");
    } finally {
      setDecidingId(null);
    }
  }

  async function toggleCapability(capability: CapabilityView) {
    setBusyCapability(capability.name);
    try {
      await api.updateCapabilityConfig(capability.name, {
        enabled: !capability.enabled,
        company_id: capabilityCompanyId ?? null,
      });
      toast.push(`${capability.description.split(" — ")[0]} ${capability.enabled ? "disabled" : "enabled"}.`, "success");
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
      const updated = await api.runCapabilityHealthCheck(capability.name, capabilityCompanyId);
      setCapabilities((prev) => prev.map((c) => (c.name === updated.name ? updated : c)));
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Health check failed.", "error");
    } finally {
      setBusyCapability(null);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={ShieldCheck}
          title="Approvals"
          description="Every external write any capability proposes waits here until you approve or reject it."
          sampleData={false}
        />

        <div className="hud-panel hud-corner flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <select
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
          >
            <option value="any">All companies</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ApprovalStatus | "")}
            className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
          >
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="executed">Executed</option>
            <option value="">All statuses</option>
          </select>
        </div>

        {loading && (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
          </div>
        )}
        {error && <p className="text-sm text-jarvis-rose">{error}</p>}

        {!loading && !error && (
          <div className="hud-panel hud-corner overflow-y-auto">
            <ul className="divide-y divide-jarvis-border/40">
              {approvals.map((req) => (
                <li key={req.id} className="flex items-start justify-between gap-3 px-5 py-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium capitalize text-jarvis-text">
                        {req.capability_name.replace("_", " ")} · {req.action_type.replace("_", " ")}
                      </p>
                      <StatusPill label={req.status} tone={STATUS_TONE[req.status]} />
                    </div>
                    {req.payload && (
                      <p className="mt-1 truncate text-xs text-jarvis-muted">{JSON.stringify(req.payload)}</p>
                    )}
                    <p className="mt-1 text-xs text-jarvis-faint">{timeAgo(req.created_at)}</p>
                  </div>
                  {req.status === "pending" && (
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        onClick={() => decide(req.id, "approve")}
                        disabled={decidingId === req.id}
                        className="press-scale flex items-center gap-1 rounded-xl border border-jarvis-emerald/50 bg-jarvis-emerald/10 px-3 py-1.5 text-xs font-semibold text-jarvis-emerald transition hover:bg-jarvis-emerald/20 disabled:opacity-50"
                      >
                        <Check className="h-3.5 w-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => decide(req.id, "reject")}
                        disabled={decidingId === req.id}
                        className="press-scale flex items-center gap-1 rounded-xl border border-jarvis-rose/50 bg-jarvis-rose/10 px-3 py-1.5 text-xs font-semibold text-jarvis-rose transition hover:bg-jarvis-rose/20 disabled:opacity-50"
                      >
                        <X className="h-3.5 w-3.5" />
                        Reject
                      </button>
                    </div>
                  )}
                </li>
              ))}
              {approvals.length === 0 && (
                <li className="px-5 py-16 text-center text-sm text-jarvis-muted">
                  Nothing waiting on you right now.
                </li>
              )}
            </ul>
          </div>
        )}

        <ModulePageHeader
          icon={HeartPulse}
          title="Capabilities"
          description="Enable/disable and check connection health per capability — permissions per action come with each integration as it's built."
          sampleData={false}
        />

        <div className="hud-panel hud-corner overflow-y-auto">
          <ul className="divide-y divide-jarvis-border/40">
            {capabilitiesLoading && (
              <li className="flex justify-center px-5 py-10">
                <Loader2 className="h-5 w-5 animate-spin text-jarvis-cyan" />
              </li>
            )}
            {!capabilitiesLoading &&
              capabilities.map((cap) => (
                <li key={cap.name} className="flex items-center justify-between gap-3 px-5 py-3.5">
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
