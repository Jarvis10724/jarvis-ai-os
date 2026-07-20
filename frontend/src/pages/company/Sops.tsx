import { useState } from "react";
import { BookOpen } from "lucide-react";
import clsx from "clsx";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import ModulePageHeader from "@/components/ModulePageHeader";
import { MOCK_SOPS } from "@/mock/sops";

export default function SopLibraryPage() {
  const [selectedId, setSelectedId] = useState(MOCK_SOPS[0]?.id ?? "");
  const selected = MOCK_SOPS.find((s) => s.id === selectedId) ?? MOCK_SOPS[0];

  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={BookOpen}
            title="SOP Library"
            description={`Standard operating procedures for ${company.name} — write once, hand off confidently.`}
          />

          <div className="flex min-h-0 flex-1 gap-4">
            <nav className="hud-panel flex w-72 shrink-0 flex-col gap-1 overflow-y-auto p-3">
              {MOCK_SOPS.map((sop) => (
                <button
                  key={sop.id}
                  onClick={() => setSelectedId(sop.id)}
                  className={clsx(
                    "rounded-xl px-3 py-2.5 text-left text-sm transition",
                    sop.id === selectedId
                      ? "border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan shadow-glow-sm"
                      : "border border-transparent text-jarvis-muted hover:border-jarvis-border hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  )}
                >
                  <p className="font-medium">{sop.title}</p>
                  <p className="text-xs opacity-70">{sop.category}</p>
                </button>
              ))}
            </nav>

            <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto p-6">
              {selected && (
                <>
                  <div className="mb-4 flex items-start justify-between">
                    <div>
                      <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                        {selected.title.toUpperCase()}
                      </h2>
                      <p className="mt-1 text-xs text-jarvis-muted">
                        {selected.category} · Owner: {selected.owner ?? "Unassigned"} · Updated{" "}
                        {selected.lastUpdated}
                      </p>
                    </div>
                  </div>
                  <p className="mb-4 text-sm leading-relaxed text-jarvis-text">{selected.summary}</p>
                  <ol className="space-y-2">
                    {selected.steps.map((step, i) => (
                      <li key={i} className="flex gap-3 text-sm text-jarvis-text">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-[11px] font-semibold text-jarvis-cyan">
                          {i + 1}
                        </span>
                        <span className="leading-relaxed">{step}</span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
