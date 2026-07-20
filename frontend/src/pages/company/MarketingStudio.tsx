import { useState } from "react";
import { Sparkles, Wand2 } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill, { type StatusTone } from "@/components/StatusPill";
import { MARKETING_TYPE_LABELS, MOCK_MARKETING_ASSETS } from "@/mock/marketing";
import type { MarketingAsset } from "@/types";

const STATUS_TONE: Record<MarketingAsset["status"], StatusTone> = {
  draft: "neutral",
  in_review: "progress",
  approved: "success",
};

export default function MarketingStudioPage() {
  const [brief, setBrief] = useState("");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  // MOCK generation — intentionally not wired to a real AI call yet (see
  // module scope note). A future `marketing_copy` plugin, built the same
  // way as the existing web_builder/logo_design/code_writer plugins, is
  // the natural place to swap this in: same input, real provider.complete().
  function generate() {
    if (!brief.trim()) return;
    setGenerating(true);
    setResult(null);
    setTimeout(() => {
      setResult(
        `[Sample draft — not AI-generated yet]\n\nHook: "${brief}"\n\nBody: Short, benefit-led copy would go here once the marketing_copy plugin is connected to a live AI provider call, following the same pattern as web_builder and logo_design.\n\nCTA: Shop now →`
      );
      setGenerating(false);
    }, 700);
  }

  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={Sparkles}
            title="AI Marketing Studio"
            description={`Draft campaigns, copy, and creative briefs for ${company.name}.`}
          />

          <div className="hud-panel hud-corner shrink-0 p-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-jarvis-muted">
              Generate a new asset (mock — not connected to AI yet)
            </p>
            <div className="flex gap-2">
              <input
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="e.g. Instagram caption announcing the Gift Box Set restock"
                className="flex-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
              />
              <button
                onClick={generate}
                disabled={generating || !brief.trim()}
                className="flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-4 py-2.5 text-sm font-medium text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
              >
                <Wand2 className="h-4 w-4" />
                {generating ? "Generating..." : "Generate"}
              </button>
            </div>
            {result && (
              <div className="mt-3 max-h-40 overflow-y-auto whitespace-pre-wrap rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-3 text-xs leading-relaxed text-jarvis-text">
                {result}
              </div>
            )}
          </div>

          <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto sm:grid-cols-2">
            {MOCK_MARKETING_ASSETS.map((asset) => (
              <div key={asset.id} className="hud-panel p-4">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-jarvis-text">{asset.title}</p>
                    <p className="text-xs text-jarvis-muted">
                      {MARKETING_TYPE_LABELS[asset.type]}
                      {asset.channel ? ` · ${asset.channel}` : ""} · {asset.createdAt}
                    </p>
                  </div>
                  <StatusPill label={asset.status.replace("_", " ")} tone={STATUS_TONE[asset.status]} />
                </div>
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-jarvis-muted">
                  {asset.preview}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
