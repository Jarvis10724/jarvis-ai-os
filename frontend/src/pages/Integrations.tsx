import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link2, Loader2, Plug, Unlink } from "lucide-react";

import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill from "@/components/StatusPill";
import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { useToast } from "@/context/ToastContext";
import { resolveWorkspace } from "@/lib/workspace";
import type { IntegrationStatus } from "@/types";

// Capabilities with a real, working server-side OAuth flow today — the
// Connect/Disconnect controls only render for these. Everything else in
// the list below is still a stub integration (see
// backend/app/integrations/*.py) and would just 501 if clicked.
const OAUTH_CAPABLE = new Set(["email", "google_calendar", "google_drive"]);

export default function IntegrationsPage() {
  const { companies, activeCompanyId, setActiveCompanyId } = useCompany();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [companyFilter, setCompanyFilter] = useState<string>(
    searchParams.get("company") ?? activeCompanyId ?? ""
  );
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listIntegrations(companyFilter || undefined);
      setIntegrations(list);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load integrations.");
    } finally {
      setLoading(false);
    }
  }, [companyFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Coming back from the OAuth callback redirect (?connected=email) —
  // acknowledge it, then drop the query param so a refresh doesn't re-fire.
  useEffect(() => {
    const connected = searchParams.get("connected");
    if (connected) {
      toast.push(`${connected.replace("_", " ")} connected.`, "success");
      searchParams.delete("connected");
      setSearchParams(searchParams, { replace: true });
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function connect(name: string) {
    setBusy(name);
    try {
      const { url } = await api.getIntegrationAuthorizeUrl(name, companyFilter || undefined);
      // Full top-level navigation — this has to leave the SPA to reach
      // Google's consent screen, then Google redirects to a backend
      // callback (never back into this page directly via fetch).
      window.location.assign(url);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to start connection.", "error");
      setBusy(null);
    }
  }

  async function disconnect(name: string) {
    setBusy(name);
    try {
      await api.disconnectIntegration(name, companyFilter || undefined);
      toast.push(`${name.replace("_", " ")} disconnected.`, "success");
      await load();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to disconnect.", "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={Plug}
          title="Integrations"
          description="Live connection status for every external service Jarvis can talk to — scoped per company."
          sampleData={false}
        />

        <div className="hud-panel hud-corner flex items-center gap-3 p-4">
          <select
            value={companyFilter}
            onChange={(e) => {
              setCompanyFilter(e.target.value);
              if (e.target.value) setActiveCompanyId(e.target.value);
            }}
            className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
          >
            <option value="">Account-wide (no company)</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <p className="text-xs text-jarvis-muted">
            Each company can connect its own Gmail account — credentials never cross workspaces.
          </p>
        </div>

        {/* Workspace-aware guidance: which integrations are typical for this kind
            of workspace. The backend scopes every connection per-company, so
            adding a new integration is data, not a redesign. */}
        {(() => {
          const selected = companies.find((c) => c.id === companyFilter) ?? null;
          if (!selected) return null;
          const ws = resolveWorkspace(selected);
          return (
            <div className="hud-panel hud-corner p-4">
              <p className="text-xs text-jarvis-muted">
                <span className="font-semibold text-jarvis-text">{selected.name}</span>{" "}
                <span className="text-jarvis-faint">· {ws.role}</span>
              </p>
              <p className="mt-1.5 text-[11px] uppercase tracking-widest text-jarvis-faint">
                Typical for this workspace
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {ws.integrationFocus.map((label) => (
                  <span
                    key={label}
                    className="rounded-lg border border-jarvis-border/70 bg-jarvis-panel2/40 px-2.5 py-1 text-[11px] text-jarvis-muted"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
          );
        })()}

        {loading && (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
          </div>
        )}
        {error && <p className="text-sm text-jarvis-rose">{error}</p>}

        {!loading && !error && (
          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto">
            <ul className="divide-y divide-jarvis-border/40">
              {integrations.map((integration) => (
                <li key={integration.name} className="flex items-center justify-between gap-3 px-5 py-3.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium capitalize text-jarvis-text">
                      {integration.name.replace("_", " ")}
                    </p>
                    <p className="text-xs text-jarvis-muted">{integration.description}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StatusPill
                      label={integration.connected ? "Connected" : "Not Connected"}
                      tone={integration.connected ? "success" : "neutral"}
                    />
                    {OAUTH_CAPABLE.has(integration.name) &&
                      (integration.connected ? (
                        <button
                          onClick={() => disconnect(integration.name)}
                          disabled={busy === integration.name}
                          className="press-scale flex items-center gap-1 rounded-xl border border-jarvis-rose/50 bg-jarvis-rose/10 px-3 py-1.5 text-xs font-semibold text-jarvis-rose transition hover:bg-jarvis-rose/20 disabled:opacity-50"
                        >
                          <Unlink className="h-3.5 w-3.5" />
                          Disconnect
                        </button>
                      ) : (
                        <button
                          onClick={() => connect(integration.name)}
                          disabled={busy === integration.name}
                          className="press-scale flex items-center gap-1 rounded-xl border border-jarvis-cyan/50 bg-jarvis-cyan/10 px-3 py-1.5 text-xs font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
                        >
                          <Link2 className="h-3.5 w-3.5" />
                          Connect
                        </button>
                      ))}
                  </div>
                </li>
              ))}
              {integrations.length === 0 && (
                <li className="px-5 py-16 text-center text-sm text-jarvis-muted">
                  No integrations registered.
                </li>
              )}
            </ul>
          </div>
        )}

        <p className="shrink-0 text-xs text-jarvis-muted">
          Connect uses Google's own consent screen — Jarvis never sees or stores your password, and refresh
          tokens are encrypted at rest. Everything except Gmail above still needs its client id/secret or
          access token added to <code>.env</code> first. See <code>docs/GETTING_STARTED.md</code>.
        </p>
    </main>
  );
}
