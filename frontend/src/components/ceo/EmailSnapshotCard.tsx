import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Mail, PlugZap } from "lucide-react";

import { api } from "@/api/client";
import type { IntegrationStatus } from "@/types";

/**
 * Unlike the other snapshot cards, there's no mock fallback here — Gmail
 * genuinely isn't wired up yet (Phase 3), so this shows a real "not
 * connected" state rather than pretending there's inbox data to show.
 */
export default function EmailSnapshotCard() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listIntegrations()
      .then((list) => {
        if (!cancelled) setStatus(list.find((i) => i.name === "email") ?? null);
      })
      .catch(() => {
        // leave status null — treated the same as "not connected" below
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-jarvis-blue" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">EMAIL</h2>
        </div>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center">
        <PlugZap className="h-5 w-5 text-jarvis-muted" />
        <p className="text-xs text-jarvis-muted">
          {status?.connected ? "Connected — inbox summaries coming with Phase 3." : "Gmail isn't connected yet."}
        </p>
        <Link to="/integrations" className="text-xs font-medium text-jarvis-cyan hover:underline">
          Go to Integrations →
        </Link>
      </div>
    </div>
  );
}
