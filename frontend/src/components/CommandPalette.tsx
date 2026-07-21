import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, FolderKanban, Search, Zap } from "lucide-react";
import clsx from "clsx";

import { GLOBAL_ITEMS, SYSTEM_ITEMS, WORKSPACE_ITEMS } from "@/components/Sidebar";
import { useCompany } from "@/context/CompanyContext";
import { useProject } from "@/context/ProjectContext";
import { isModuleVisibleForCompany } from "@/lib/companyModules";
import { QUICK_ACTIONS } from "@/lib/quickActions";

interface PaletteEntry {
  key: string;
  label: string;
  description: string;
  icon: typeof Search;
  group: "Go to" | "Projects" | "Quick Actions";
  run: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

// Global "go anywhere / do anything" overlay — distinct from the top bar's
// Memory search. Reuses Sidebar's existing route lists and QuickActions'
// existing action list rather than maintaining a third registry.
export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const { projects } = useProject();

  const entries = useMemo<PaletteEntry[]>(() => {
    const navItems = [
      ...GLOBAL_ITEMS.filter((i) => isModuleVisibleForCompany(i.category, activeCompany)),
      ...(activeCompany ? WORKSPACE_ITEMS : []),
      ...SYSTEM_ITEMS,
    ];
    const navEntries: PaletteEntry[] = navItems.map((item) => ({
      key: `nav:${item.to}`,
      label: item.label,
      description: item.to,
      icon: item.icon,
      group: "Go to",
      run: () => navigate(item.to),
    }));
    // Projects in the active company — jump straight to a project's workspace.
    const projectEntries: PaletteEntry[] = projects.map((p) => ({
      key: `project:${p.id}`,
      label: p.name,
      description: p.is_default ? "Default project" : "Project",
      icon: FolderKanban,
      group: "Projects",
      run: () => navigate(`/projects/${p.id}`),
    }));
    const actionEntries: PaletteEntry[] = QUICK_ACTIONS.map((action) => ({
      key: `action:${action.key}`,
      label: action.label,
      description: action.description,
      icon: action.icon,
      group: "Quick Actions",
      // Opens the action's persistent streaming workspace.
      run: () => navigate(`/studio/${action.pluginName}`),
    }));
    return [...navEntries, ...projectEntries, ...actionEntries];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCompany, projects, navigate]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) => e.label.toLowerCase().includes(q) || e.description.toLowerCase().includes(q)
    );
  }, [entries, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query, open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  function activate(entry: PaletteEntry | undefined) {
    if (!entry) return;
    onClose();
    entry.run();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      activate(filtered[activeIndex]);
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  let runningIndex = -1;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="hud-panel hud-corner fixed left-1/2 top-[18vh] z-50 w-full max-w-lg -translate-x-1/2 overflow-hidden shadow-elevated-lg"
          >
            <div className="flex items-center gap-3 border-b border-jarvis-border/60 px-4 py-3.5">
              <Search className="h-4 w-4 shrink-0 text-jarvis-muted" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Jump to a page, or run a quick action..."
                className="w-full bg-transparent text-sm text-jarvis-text placeholder:text-jarvis-faint focus:outline-none"
              />
              <kbd className="shrink-0 rounded-md border border-jarvis-border/70 px-1.5 py-0.5 text-[10px] text-jarvis-faint">
                ESC
              </kbd>
            </div>

            <div className="max-h-[50vh] overflow-y-auto p-2">
              {filtered.length === 0 && (
                <p className="px-3 py-8 text-center text-sm text-jarvis-muted">No matches.</p>
              )}
              {(["Go to", "Projects", "Quick Actions"] as const).map((group) => {
                const groupEntries = filtered.filter((e) => e.group === group);
                if (groupEntries.length === 0) return null;
                return (
                  <div key={group} className="mb-1">
                    <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-jarvis-faint">
                      {group}
                    </p>
                    {groupEntries.map((entry) => {
                      runningIndex += 1;
                      const isActive = runningIndex === activeIndex;
                      const Icon = entry.icon;
                      return (
                        <button
                          key={entry.key}
                          onMouseEnter={() => setActiveIndex(runningIndex)}
                          onClick={() => activate(entry)}
                          className={clsx(
                            "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors duration-100",
                            isActive
                              ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                              : "text-jarvis-text hover:bg-jarvis-panel2/60"
                          )}
                        >
                          <Icon className="h-4 w-4 shrink-0" />
                          <span className="min-w-0 flex-1 truncate">{entry.label}</span>
                          {isActive && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan" />}
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-1.5 border-t border-jarvis-border/60 px-4 py-2.5 text-[10px] text-jarvis-faint">
              <Zap className="h-3 w-3" />
              <span>Cmd/Ctrl+K to open · ↑↓ to move · Enter to select</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
