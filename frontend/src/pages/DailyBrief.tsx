import { useEffect, useState } from "react";
import { Loader2, RefreshCw, Sunrise } from "lucide-react";

import ModulePageHeader from "@/components/ModulePageHeader";
import SampleDataBadge from "@/components/SampleDataBadge";
import { api, ApiError } from "@/api/client";
import { useCompany } from "@/context/CompanyContext";
import { generateDailyBriefingContent } from "@/lib/dailyBriefing";

function formatGeneratedAt(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function DailyBriefPage() {
  const { companies } = useCompany();
  const [briefing, setBriefing] = useState<{ content: string; generated_at: string | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getLatestDailyBriefing()
      .then(setBriefing)
      .catch(() => setBriefing(null))
      .finally(() => setLoading(false));
  }, []);

  async function generateNow() {
    setGenerating(true);
    setError(null);
    try {
      const content = await generateDailyBriefingContent(companies);
      const saved = await api.saveDailyBriefing(content);
      setBriefing(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate the briefing.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={Sunrise}
          title="Daily Brief"
          description={`Good morning — here's what matters today across ${companies.length || "your"} ${companies.length === 1 ? "company" : "companies"}.`}
          sampleData={false}
        />

        <div className="hud-panel hud-corner flex-1 overflow-y-auto p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {briefing?.generated_at && (
                <span className="text-xs text-jarvis-muted">Generated {formatGeneratedAt(briefing.generated_at)}</span>
              )}
              <SampleDataBadge label="AI News: Sample" />
            </div>
            <button
              onClick={generateNow}
              disabled={generating}
              className="press-scale flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-1.5 text-xs font-medium text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
            >
              {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              {briefing ? "Regenerate" : "Generate Daily Briefing"}
            </button>
          </div>

          {error && <p className="mb-3 text-xs text-jarvis-rose">{error}</p>}

          {loading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
            </div>
          ) : briefing ? (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-jarvis-text">{briefing.content}</pre>
          ) : (
            <p className="py-10 text-center text-sm text-jarvis-muted">
              No briefing has been generated yet — click "Generate Daily Briefing" above. Once scheduled, this'll be
              waiting for you automatically every morning.
            </p>
          )}
        </div>

        <div className="hud-panel hud-corner p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-jarvis-text">Companies</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {companies.map((c) => (
              <div key={c.id} className="rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-4">
                <p className="text-sm font-medium text-jarvis-text">{c.name}</p>
                <p className="text-xs text-jarvis-muted">
                  {c.industry ?? "No industry set"}
                  {c.divisions.length ? ` · ${c.divisions.join(", ")}` : ""}
                </p>
              </div>
            ))}
            {companies.length === 0 && (
              <p className="text-sm text-jarvis-muted">No companies yet — use the switcher in the sidebar.</p>
            )}
          </div>
        </div>
    </main>
  );
}
