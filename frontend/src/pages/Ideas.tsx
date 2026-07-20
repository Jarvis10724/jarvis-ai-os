import { useState } from "react";
import { Lightbulb } from "lucide-react";

import ModulePageHeader from "@/components/ModulePageHeader";
import { IDEA_COLUMNS, MOCK_IDEAS } from "@/mock/ideas";
import type { BusinessIdea, IdeaStage } from "@/types";

export default function BusinessIdeaIncubatorPage() {
  const [ideas, setIdeas] = useState<BusinessIdea[]>(MOCK_IDEAS);

  function moveIdea(id: string, stage: IdeaStage) {
    setIdeas((prev) => prev.map((i) => (i.id === id ? { ...i, stage } : i)));
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={Lightbulb}
          title="Business Idea Incubator"
          description="Where new venture ideas go from spark to launch — the natural home for Greener Capitol's Future Ventures division."
        />

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {IDEA_COLUMNS.map((col) => {
            const items = ideas.filter((i) => i.stage === col.key);
            return (
              <div key={col.key} className="hud-panel flex min-h-0 flex-col overflow-hidden">
                <div className="flex items-center justify-between border-b border-jarvis-border/70 px-4 py-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-jarvis-text">
                    {col.label}
                  </h3>
                  <span className="text-xs text-jarvis-muted">{items.length}</span>
                </div>
                <div className="flex-1 space-y-2 overflow-y-auto p-3">
                  {items.map((idea) => (
                    <div key={idea.id} className="rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/50 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-jarvis-text">{idea.title}</p>
                        {idea.score !== null && (
                          <span className="shrink-0 rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-1.5 py-0.5 text-[10px] font-semibold text-jarvis-cyan">
                            {idea.score}/10
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-jarvis-muted">{idea.description}</p>
                      {idea.division && (
                        <span className="mt-2 inline-block rounded-full border border-jarvis-border/70 px-2 py-0.5 text-[10px] text-jarvis-muted">
                          {idea.division}
                        </span>
                      )}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {IDEA_COLUMNS.filter((c) => c.key !== idea.stage).map((c) => (
                          <button
                            key={c.key}
                            onClick={() => moveIdea(idea.id, c.key)}
                            className="rounded-md border border-transparent px-1.5 py-0.5 text-[10px] text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
                          >
                            → {c.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  {items.length === 0 && (
                    <p className="px-2 py-6 text-center text-xs text-jarvis-muted">Empty</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
    </main>
  );
}
