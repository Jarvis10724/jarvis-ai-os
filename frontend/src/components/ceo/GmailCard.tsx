import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Loader2, Mail, PlugZap, RefreshCw, Star } from "lucide-react";
import clsx from "clsx";

import { api } from "@/api/client";
import type { ApprovalRequestView, GmailMessage } from "@/types";

const AUTO_REFRESH_MS = 60_000;

function gmailWebLink(messageId: string): string {
  return `https://mail.google.com/mail/u/0/#all/${messageId}`;
}

/**
 * Real Gmail data — unread messages and emails awaiting approval both come
 * straight from the API. Important-labeled mail (Gmail's own priority
 * signal, not a heuristic we invented) sorts first with a star. Polls
 * every 60s so the count stays live without a manual refresh. "Follow-ups
 * due" has no real tracking mechanism yet (Gmail's API doesn't expose
 * "awaiting reply" natively), so it's shown honestly rather than faked.
 */
export default function GmailCard({ companyId }: { companyId?: string } = {}) {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [unread, setUnread] = useState<GmailMessage[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequestView[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const firstLoad = useRef(true);

  const load = useCallback(async () => {
    if (firstLoad.current) setLoading(true);
    else setRefreshing(true);
    try {
      const messages = await api.listGmailMessages({ companyId, unreadOnly: true, maxResults: 15 });
      const sorted = [...messages].sort((a, b) => Number(b.important) - Number(a.important));
      setUnread(sorted);
      setConnected(true);
    } catch {
      setConnected(false);
    }
    try {
      const approvals = await api.listApprovals({ companyId: companyId ?? "any", status: "pending" });
      setPendingApprovals(approvals.filter((a) => a.capability_name === "email"));
    } catch {
      // leave empty
    }
    firstLoad.current = false;
    setLoading(false);
    setRefreshing(false);
  }, [companyId]);

  useEffect(() => {
    firstLoad.current = true;
    load();
    const interval = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-jarvis-blue" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">GMAIL</h2>
        </div>
        <div className="flex items-center gap-2">
          {connected && <span className="font-data text-xs text-jarvis-muted">{unread.length} unread</span>}
          <button
            onClick={() => load()}
            disabled={loading || refreshing}
            title="Refresh now"
            className="press-scale rounded-lg p-1 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-cyan disabled:opacity-40"
          >
            <RefreshCw className={clsx("h-3.5 w-3.5", refreshing && "animate-spin")} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 space-y-2 p-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-6 w-full animate-pulse rounded-lg bg-jarvis-panel2/50" />
          ))}
        </div>
      ) : connected === false ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center">
          <PlugZap className="h-5 w-5 text-jarvis-muted" />
          <p className="text-xs text-jarvis-muted">Gmail isn't connected yet.</p>
          <Link to="/integrations" className="text-xs font-medium text-jarvis-cyan hover:underline">
            Go to Integrations →
          </Link>
        </div>
      ) : (
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {pendingApprovals.length > 0 && (
            <div className="rounded-lg border border-jarvis-amber/30 bg-jarvis-amber/5 px-2.5 py-1.5 text-xs text-jarvis-text">
              {pendingApprovals.length} email action{pendingApprovals.length === 1 ? "" : "s"} waiting on your approval —{" "}
              <Link to="/approvals" className="font-medium text-jarvis-cyan hover:underline">
                review →
              </Link>
            </div>
          )}
          <ul className="space-y-1.5">
            {unread.slice(0, 6).map((m) => (
              <li
                key={m.id}
                className={clsx(
                  "group flex items-center gap-1.5 truncate rounded-lg border px-2.5 py-1.5 text-xs",
                  m.important
                    ? "border-jarvis-amber/30 bg-jarvis-amber/5"
                    : "border-jarvis-border/60 bg-jarvis-panel2/40"
                )}
              >
                {m.important && <Star className="h-3 w-3 shrink-0 fill-jarvis-amber text-jarvis-amber" />}
                <span className="min-w-0 flex-1 truncate">
                  <span className="text-jarvis-text">{m.subject || "(no subject)"}</span>
                  <span className="text-jarvis-muted"> — {m.from}</span>
                </span>
                <a
                  href={gmailWebLink(m.id)}
                  target="_blank"
                  rel="noreferrer"
                  title="Open in Gmail"
                  className="shrink-0 text-jarvis-muted opacity-0 transition hover:text-jarvis-cyan group-hover:opacity-100"
                >
                  <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            ))}
            {unread.length === 0 && <p className="text-xs text-jarvis-muted">Inbox zero — no unread mail.</p>}
          </ul>
          <p className="flex items-center gap-1 text-[10px] text-jarvis-faint">
            {refreshing && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
            Follow-ups due: not tracked yet. Auto-refreshes every minute.
          </p>
        </div>
      )}
    </div>
  );
}
