import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Menu, Moon, Search, Sun, Zap } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

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
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

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
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-jarvis-border/60 bg-jarvis-panel/40 px-4 backdrop-blur-2xl sm:gap-4 sm:px-6">
      <button
        onClick={onOpenMobileNav}
        className="press-scale rounded-lg p-2 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

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
          className="press-scale relative rounded-xl border border-jarvis-border bg-jarvis-panel2/50 p-2.5 text-jarvis-muted transition-all duration-200 hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
        >
          <Bell className="h-4 w-4" />
          {unreadNotifications > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-jarvis-rose text-[10px] font-bold text-white shadow-glow-sm">
              {unreadNotifications}
            </span>
          )}
        </button>

        <button
          onClick={toggleDark}
          className="press-scale rounded-xl border border-jarvis-border bg-jarvis-panel2/50 p-2.5 text-jarvis-muted transition-all duration-200 hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <div className="mx-0.5 h-8 w-px bg-jarvis-border/60 sm:mx-1" />

        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-xs font-bold text-jarvis-cyan shadow-glow-sm">
            {initials}
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="press-scale rounded-xl p-2 text-jarvis-muted transition-colors duration-200 hover:text-jarvis-rose"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
