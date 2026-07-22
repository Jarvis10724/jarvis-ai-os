import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Menu, Moon, Search, Sun, Zap } from "lucide-react";
import clsx from "clsx";

import { api } from "@/api/client";
import JarvisCore from "@/components/JarvisCore";
import { useAuth } from "@/context/AuthContext";
import { useCompany } from "@/context/CompanyContext";
import { useDashboardUI } from "@/context/DashboardUIContext";
import { useTheme } from "@/context/ThemeContext";
import { useCoreState } from "@/hooks/useCoreState";
import { useWorkspace } from "@/hooks/useWorkspace";

interface TopNavProps {
  onToggleNotifications: () => void;
  onToggleQuickActions: () => void;
  onOpenMobileNav: () => void;
  unreadNotifications: number;
}

export default function TopNav({
  onToggleNotifications,
  onToggleQuickActions,
  onOpenMobileNav,
  unreadNotifications,
}: TopNavProps) {
  const { user, logout } = useAuth();
  const { dark, toggleDark } = useTheme();
  const { activeCompany, activeCompanyId } = useCompany();
  const workspace = useWorkspace();
  const { openCoreCommand, openWorkspaceSwitcher } = useDashboardUI();
  const coreState = useCoreState();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  // Real unread count so the bell means something (pending approvals for the
  // active workspace) — refreshed on workspace switch, not fabricated.
  const [alerts, setAlerts] = useState(0);
  useEffect(() => {
    let cancelled = false;
    api
      .listApprovals({ companyId: activeCompanyId ?? "any", status: "pending" })
      .then((list) => !cancelled && setAlerts(list.length))
      .catch(() => !cancelled && setAlerts(0));
    return () => {
      cancelled = true;
    };
  }, [activeCompanyId]);

  const badge = Math.max(unreadNotifications, alerts);
  const dba = activeCompany?.divisions?.[0];

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    navigate(`/memory?q=${encodeURIComponent(trimmed)}`);
  }

  const initials = (user?.full_name || user?.email || "J")
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="pt-safe flex min-h-16 shrink-0 items-center gap-3 border-b border-jarvis-border/60 bg-jarvis-panel/40 px-4 backdrop-blur-2xl sm:gap-4 sm:px-6">
      <button
        onClick={onOpenMobileNav}
        aria-label="Open navigation"
        className="press-scale flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* AI Core — the central brain, present on every screen. Tap to command
          Jarvis (real chat/AI pipeline); the orb reflects live state
          (idle/thinking/waiting-for-approval). */}
      <button
        onClick={openCoreCommand}
        title="Ask Jarvis — command the AI Core"
        aria-label="Ask Jarvis"
        className="press-scale flex shrink-0 items-center gap-2 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 py-1 pl-1 pr-2.5 transition hover:border-[color:var(--ws-accent-soft)] sm:pr-3"
      >
        <JarvisCore state={coreState} size={30} />
        <span className="hidden text-xs font-semibold text-jarvis-text sm:inline">Ask Jarvis</span>
      </button>

      {/* Active-workspace chip — present on every screen (its monogram + name +
          DBA), and tapping it opens the global workspace switcher for a fast,
          state-preserving switch between businesses. */}
      {activeCompany && (
        <button
          onClick={openWorkspaceSwitcher}
          title="Switch workspace"
          className="press-scale flex min-w-0 flex-1 items-center gap-2 rounded-xl border py-1.5 pl-2 pr-3 text-left transition sm:max-w-[220px] sm:flex-none"
          style={{ borderColor: "var(--ws-accent-soft)", backgroundColor: "var(--ws-accent-faint)" }}
        >
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg font-display text-[11px] font-bold"
            style={{ backgroundColor: "var(--ws-accent-faint)", color: "var(--ws-accent)" }}
          >
            {workspace.monogram}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-xs font-semibold leading-tight text-jarvis-text">
              {activeCompany.name}
            </span>
            {dba && (
              <span className="block truncate text-[10px] leading-tight text-jarvis-muted">{dba}</span>
            )}
          </span>
        </button>
      )}

      <form onSubmit={handleSearchSubmit} className="relative hidden w-full max-w-md sm:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-jarvis-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Jarvis's memory..."
          className="w-full rounded-xl border border-jarvis-border bg-jarvis-panel2/50 py-2 pl-9 pr-4 text-sm text-jarvis-text placeholder:text-jarvis-faint transition-colors duration-200 focus:border-jarvis-cyan/50 focus:bg-jarvis-panel2/80 focus:outline-none focus:ring-1 focus:ring-jarvis-cyan/30"
        />
      </form>

      <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
        <button
          onClick={onToggleQuickActions}
          className="press-scale flex items-center gap-2 rounded-xl border border-jarvis-cyan/30 bg-jarvis-cyan/10 px-2.5 py-2 text-xs font-semibold uppercase tracking-wider text-jarvis-cyan transition-all duration-200 hover:bg-jarvis-cyan/20 hover:shadow-glow-sm sm:px-3"
        >
          <Zap className="h-4 w-4" />
          <span className="hidden sm:inline">Quick Actions</span>
        </button>

        <button
          onClick={onToggleNotifications}
          aria-label={badge > 0 ? `Notifications — ${badge} need attention` : "Notifications"}
          className={clsx(
            "press-scale relative rounded-xl border p-2.5 transition-all duration-200",
            badge > 0
              ? "border-jarvis-amber/50 bg-jarvis-amber/10 text-jarvis-amber hover:bg-jarvis-amber/20"
              : "border-jarvis-border bg-jarvis-panel2/50 text-jarvis-muted hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
          )}
        >
          <Bell className="h-4 w-4" />
          {badge > 0 && (
            <>
              {/* Attention pulse so alerts read as important, not decorative. */}
              <span className="absolute -right-1 -top-1 h-4 w-4 animate-ping rounded-full bg-jarvis-amber/60" />
              <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-jarvis-amber text-[10px] font-bold text-jarvis-bg shadow-glow-sm">
                {badge}
              </span>
            </>
          )}
        </button>

        <button
          onClick={toggleDark}
          className="press-scale rounded-xl border border-jarvis-border bg-jarvis-panel2/50 p-2.5 text-jarvis-muted transition-all duration-200 hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <div className="mx-1 hidden h-8 w-px bg-jarvis-border/60 sm:block" />

        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Decorative user initials — hidden on phones to give the active-
              company chip room; sign-out stays available at all sizes. */}
          <div className="hidden h-9 w-9 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-xs font-bold text-jarvis-cyan shadow-glow-sm sm:flex">
            {initials}
          </div>
          <button
            onClick={logout}
            title="Sign out"
            aria-label="Sign out"
            className="press-scale rounded-xl p-2 text-jarvis-muted transition-colors duration-200 hover:text-jarvis-rose"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
