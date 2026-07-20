import { useState } from "react";
import { Loader2, Zap } from "lucide-react";

import ModulePageHeader from "@/components/ModulePageHeader";
import { api, ApiError } from "@/api/client";

export default function AutomationPage() {
  const [taskDescription, setTaskDescription] = useState("");
  const [frequency, setFrequency] = useState("");
  const [designing, setDesigning] = useState(false);
  const [design, setDesign] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Real call to the backend's `automation` plugin — designs a workflow,
  // it doesn't execute one yet (see docs/ROADMAP.md: background execution
  // needs a worker, which Redis is already provisioned for).
  async function designWorkflow() {
    if (!taskDescription.trim()) return;
    setDesigning(true);
    setError(null);
    setDesign(null);
    try {
      const result = await api.runPlugin("automation", {
        task_description: taskDescription,
        frequency: frequency || undefined,
      });
      setDesign(String(result.output));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to design the automation — check your AI provider key in .env.");
    } finally {
      setDesigning(false);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={Zap}
          title="Automation"
          description="Design repeatable workflows for repetitive work — real AI call to the automation plugin."
          sampleData={false}
        />

        <div className="hud-panel hud-corner shrink-0 p-4">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row">
            <input
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              placeholder="Describe the repetitive task, e.g. 'weekly inventory report to email'"
              className="flex-1 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none"
            />
            <input
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              placeholder="Frequency (optional) — e.g. weekly"
              className="w-full rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-muted focus:border-jarvis-cyan/50 focus:outline-none sm:w-56"
            />
          </div>
          <button
            onClick={designWorkflow}
            disabled={designing || !taskDescription.trim()}
            className="flex items-center gap-1.5 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-4 py-2.5 text-sm font-medium text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
          >
            {designing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {designing ? "Designing..." : "Design Workflow"}
          </button>
          {error && <p className="mt-2 text-xs text-jarvis-rose">{error}</p>}
        </div>

        <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto p-4">
          {design ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-jarvis-text">{design}</p>
          ) : (
            <p className="text-sm text-jarvis-muted">
              Describe a repetitive task above and Jarvis will design the trigger, steps, and failure
              handling for it. Running the resulting workflow on a schedule is on the roadmap — for now
              this designs it so you (or a VA) can execute it manually.
            </p>
          )}
        </div>
    </main>
  );
}
