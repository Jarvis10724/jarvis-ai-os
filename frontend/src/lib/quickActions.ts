import { Code2, Globe, Palette, Search, ShoppingBag, Workflow } from "lucide-react";

import { api, ApiError } from "@/api/client";
import type { usePrompt } from "@/context/PromptContext";
import type { PromptField } from "@/context/PromptContext";
import type { useToast } from "@/context/ToastContext";

export interface QuickAction {
  key: string;
  label: string;
  description: string;
  icon: typeof Globe;
  // Matches both the builtin plugin name AND the workspace action slug
  // (see backend app.core.workspace_actions) — Quick Actions now open a
  // persistent workspace at /studio/:pluginName.
  pluginName: string;
  promptTitle: string;
  fields: PromptField[];
}

// Shared by QuickActions.tsx (grid modal) and CommandPalette.tsx (⌘K) so
// both surfaces run the exact same prompt-for-input + api.runPlugin flow
// instead of two copies drifting apart.
export const QUICK_ACTIONS: QuickAction[] = [
  {
    key: "web",
    label: "Build a Website",
    description: "Plan pages, copy, and a starter layout",
    icon: Globe,
    pluginName: "web_builder",
    promptTitle: "Build a Website",
    fields: [{ key: "brief", label: "Describe the site/business", multiline: true }],
  },
  {
    key: "logo",
    label: "Design a Logo",
    description: "Generate brand concepts and a starter mark",
    icon: Palette,
    pluginName: "logo_design",
    promptTitle: "Design a Logo",
    fields: [
      { key: "brand_name", label: "Brand name" },
      { key: "brief", label: "Describe the brand (industry, audience, tone)", multiline: true },
    ],
  },
  {
    key: "product",
    label: "Create a Product",
    description: "Spec, pricing, and launch checklist",
    icon: ShoppingBag,
    pluginName: "product_creation",
    promptTitle: "Create a Product",
    fields: [{ key: "idea", label: "Describe the product idea", multiline: true }],
  },
  {
    key: "research",
    label: "Deep Research",
    description: "Structured multi-angle synthesis",
    icon: Search,
    pluginName: "deep_research",
    promptTitle: "Deep Research",
    fields: [{ key: "question", label: "What should Jarvis research?", multiline: true }],
  },
  {
    key: "code",
    label: "Write Code",
    description: "Generate code from a spec",
    icon: Code2,
    pluginName: "code_writer",
    promptTitle: "Write Code",
    fields: [{ key: "spec", label: "Describe what to build", multiline: true }],
  },
  {
    key: "automation",
    label: "Automate a Task",
    description: "Design a repeatable workflow",
    icon: Workflow,
    pluginName: "automation",
    promptTitle: "Automate a Task",
    fields: [{ key: "task_description", label: "Describe the repetitive task", multiline: true }],
  },
];

/**
 * Prompts for the action's inputs, then runs it via the plugin API —
 * cancel-aware (a null result from `prompt` means the user backed out,
 * distinct from submitting blank fields). Callers should close their own
 * overlay (QuickActions modal / CommandPalette) before calling this, same
 * as the original QuickActions.tsx behavior.
 */
export async function runQuickAction(
  action: QuickAction,
  prompt: ReturnType<typeof usePrompt>,
  toast: ReturnType<typeof useToast>
): Promise<void> {
  const values = await prompt({ title: action.promptTitle, fields: action.fields, confirmLabel: "Run" });
  if (values === null) return;
  if (Object.values(values).every((v) => !v.trim())) {
    toast.push(`${action.label} cancelled — no input provided.`, "info");
    return;
  }
  try {
    await api.runPlugin(action.pluginName, values);
    toast.push(`${action.label} is running — check Recent Tasks for progress.`, "success");
  } catch (err) {
    toast.push(err instanceof ApiError ? err.message : "Failed to start the action.", "error");
  }
}
