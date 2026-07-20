import { useEffect, useState } from "react";
import { Blocks, Loader2, Play } from "lucide-react";

import ModulePageHeader from "@/components/ModulePageHeader";
import { api, ApiError } from "@/api/client";
import { usePrompt } from "@/context/PromptContext";
import { useToast } from "@/context/ToastContext";
import type { PluginInfo } from "@/types";

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningPlugin, setRunningPlugin] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<{ plugin: string; output: string } | null>(null);
  const prompt = usePrompt();
  const toast = useToast();

  useEffect(() => {
    api
      .listPlugins()
      .then(setPlugins)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load plugins."))
      .finally(() => setLoading(false));
  }, []);

  async function quickRun(plugin: PluginInfo) {
    const values = await prompt({
      title: `Quick-run "${plugin.name}"`,
      fields: [{ key: "input", label: "Main input", multiline: true }],
      confirmLabel: "Run",
    });
    if (values === null || !values.input.trim()) return;
    setRunningPlugin(plugin.name);
    setLastResult(null);
    try {
      // Every plugin's primary argument name differs (brief/idea/question/spec/...),
      // so this generic runner tries the most common one for known plugins.
      const argKey =
        {
          web_builder: "brief",
          logo_design: "brief",
          product_creation: "idea",
          deep_research: "question",
          code_writer: "spec",
          project_management: "goal",
          automation: "task_description",
        }[plugin.name] ?? "input";
      const result = await api.runPlugin(plugin.name, { [argKey]: values.input });
      setLastResult({ plugin: plugin.name, output: String(result.output ?? result.message) });
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Plugin run failed.", "error");
    } finally {
      setRunningPlugin(null);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={Blocks}
          title="Plugins"
          description="Every capability Jarvis can run — live from the backend registry, not mock data."
          sampleData={false}
        />

        {loading && (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-jarvis-cyan" />
          </div>
        )}
        {error && <p className="text-sm text-jarvis-rose">{error}</p>}

        {!loading && !error && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plugins.map((plugin) => (
              <div key={plugin.name} className="hud-panel p-4">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-jarvis-text">{plugin.name}</p>
                    <p className="text-[10px] uppercase tracking-wide text-jarvis-muted">
                      v{plugin.version}
                    </p>
                  </div>
                  <button
                    onClick={() => quickRun(plugin)}
                    disabled={runningPlugin === plugin.name}
                    className="flex items-center gap-1 rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-2 py-1 text-[10px] font-medium text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-50"
                  >
                    <Play className="h-3 w-3" />
                    {runningPlugin === plugin.name ? "Running..." : "Run"}
                  </button>
                </div>
                <p className="text-xs leading-relaxed text-jarvis-muted">{plugin.description}</p>
              </div>
            ))}
            {plugins.length === 0 && (
              <p className="text-sm text-jarvis-muted">No plugins registered.</p>
            )}
          </div>
        )}

        {lastResult && (
          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto p-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-jarvis-muted">
              Output — {lastResult.plugin}
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-jarvis-text">
              {lastResult.output}
            </p>
          </div>
        )}
    </main>
  );
}
