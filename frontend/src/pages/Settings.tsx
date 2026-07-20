import { useEffect, useState } from "react";
import { Loader2, Settings as SettingsIcon } from "lucide-react";
import clsx from "clsx";

import ModulePageHeader from "@/components/ModulePageHeader";
import ShopifyStatusCard from "@/components/ShopifyStatusCard";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { useToast } from "@/context/ToastContext";
import { api, ApiError } from "@/api/client";
import type { PluginInfo, PluginSettingRead } from "@/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { dark, toggleDark } = useTheme();
  const toast = useToast();

  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [settings, setSettings] = useState<Record<string, PluginSettingRead>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listPlugins(), api.listPluginSettings()])
      .then(([pluginList, settingList]) => {
        setPlugins(pluginList);
        setSettings(Object.fromEntries(settingList.map((s) => [s.plugin_name, s])));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load settings."))
      .finally(() => setLoading(false));
  }, []);

  async function toggleEnabled(pluginName: string, currentlyEnabled: boolean) {
    const next = !currentlyEnabled;
    setSettings((prev) => ({
      ...prev,
      [pluginName]: { plugin_name: pluginName, enabled: next, config: prev[pluginName]?.config ?? {} },
    }));
    try {
      await api.updatePluginSettings(pluginName, { enabled: next });
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to update plugin setting.", "error");
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModulePageHeader
          icon={SettingsIcon}
          title="Settings"
          description="Account, appearance, and per-plugin controls."
          sampleData={false}
        />

        <div className="hud-panel hud-corner shrink-0 p-5">
          <p className="mb-3 text-xs uppercase tracking-wide text-jarvis-muted">Account</p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-jarvis-text">{user?.full_name || "No name set"}</p>
              <p className="text-xs text-jarvis-muted">{user?.email}</p>
            </div>
            <button
              onClick={logout}
              className="rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-3 py-2 text-xs font-medium text-jarvis-muted transition hover:border-jarvis-rose/40 hover:text-jarvis-rose"
            >
              Sign Out
            </button>
          </div>
        </div>

        <div className="hud-panel hud-corner shrink-0 p-5">
          <p className="mb-3 text-xs uppercase tracking-wide text-jarvis-muted">Appearance</p>
          <div className="flex items-center justify-between">
            <p className="text-sm text-jarvis-text">Dark mode</p>
            <button
              onClick={toggleDark}
              className={clsx(
                "rounded-full border px-3 py-1 text-xs font-medium transition",
                dark
                  ? "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
                  : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted"
              )}
            >
              {dark ? "On" : "Off"}
            </button>
          </div>
        </div>

        <ShopifyStatusCard />

        <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto p-5">
          <p className="mb-3 text-xs uppercase tracking-wide text-jarvis-muted">Plugins</p>
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-jarvis-cyan" />
            </div>
          )}
          {error && <p className="text-sm text-jarvis-rose">{error}</p>}
          {!loading && !error && (
            <ul className="divide-y divide-jarvis-border/40">
              {plugins.map((plugin) => {
                const enabled = settings[plugin.name]?.enabled ?? true;
                return (
                  <li key={plugin.name} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-jarvis-text">{plugin.name}</p>
                      <p className="text-xs text-jarvis-muted">{plugin.description}</p>
                    </div>
                    <button
                      onClick={() => toggleEnabled(plugin.name, enabled)}
                      className={clsx(
                        "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition",
                        enabled
                          ? "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald"
                          : "border-jarvis-border bg-jarvis-panel2/60 text-jarvis-muted"
                      )}
                    >
                      {enabled ? "Enabled" : "Disabled"}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
    </main>
  );
}
