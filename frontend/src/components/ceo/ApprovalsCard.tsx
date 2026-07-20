import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ShieldCheck, X } from "lucide-react";

import { api, ApiError } from "@/api/client";
import { useToast } from "@/context/ToastContext";
import type { ApprovalRequestView } from "@/types";

/**
 * Every action Jarvis wants to take (send an email, create a calendar
 * event, ...) lands here as a pending ApprovalRequest before anything
 * external happens — real data, same approve/reject flow as the full
 * /approvals page, just the 5 most recent so it fits on the dashboard.
 */
export default function ApprovalsCard({ companyId }: { companyId?: string } = {}) {
  const toast = useToast();
  const [approvals, setApprovals] = useState<ApprovalRequestView[]>([]);
  const [loading, setLoading] = useState(true);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listApprovals({ companyId: companyId ?? "any", status: "pending" });
      setApprovals(list);
    } catch {
      // leave empty — the card still renders its shell
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(id: string, action: "approve" | "reject") {
    setDecidingId(id);
    try {
      if (action === "approve") await api.approveRequest(id);
      else await api.rejectRequest(id);
      toast.push(action === "approve" ? "Approved." : "Rejected.", "success");
      await load();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : `Failed to ${action}.`, "error");
    } finally {
      setDecidingId(null);
    }
  }

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-jarvis-cyan" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            PENDING APPROVALS
          </h2>
        </div>
        {approvals.length > 0 && (
          <span className="rounded-full border border-jarvis-amber/40 bg-jarvis-amber/10 px-2 py-0.5 font-data text-xs text-jarvis-amber">
            {approvals.length}
          </span>
        )}
      </div>

      <ul className="flex-1 space-y-2 overflow-y-auto p-4">
        {loading &&
          [0, 1].map((i) => <div key={i} className="h-10 w-full animate-pulse rounded-xl bg-jarvis-panel2/50" />)}
        {!loading &&
          approvals.slice(0, 5).map((req) => (
            <li
              key={req.id}
              className="flex items-center justify-between gap-2 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2"
            >
              <span className="min-w-0 flex-1 truncate text-xs capitalize text-jarvis-text">
                {req.capability_name.replace("_", " ")} · {req.action_type.replace("_", " ")}
              </span>
              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  onClick={() => decide(req.id, "approve")}
                  disabled={decidingId === req.id}
                  className="press-scale rounded-lg border border-jarvis-emerald/50 bg-jarvis-emerald/10 p-1 text-jarvis-emerald transition hover:bg-jarvis-emerald/20 disabled:opacity-50"
                >
                  <Check className="h-3 w-3" />
                </button>
                <button
                  onClick={() => decide(req.id, "reject")}
                  disabled={decidingId === req.id}
                  className="press-scale rounded-lg border border-jarvis-rose/50 bg-jarvis-rose/10 p-1 text-jarvis-rose transition hover:bg-jarvis-rose/20 disabled:opacity-50"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </li>
          ))}
        {!loading && approvals.length === 0 && (
          <p className="p-2 text-xs text-jarvis-muted">Nothing waiting on you right now.</p>
        )}
      </ul>
      <Link
        to="/approvals"
        className="press-scale border-t border-jarvis-border/60 px-4 py-2.5 text-center text-xs font-medium text-jarvis-cyan hover:bg-jarvis-panel2/40"
      >
        View all →
      </Link>
    </div>
  );
}
