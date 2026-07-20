import { useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  BrainCircuit,
  Compass,
  MessageSquare,
  Plug,
  Rocket,
  Settings as SettingsIcon,
  ShieldCheck,
  Zap,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

import JarvisCore from "@/components/JarvisCore";
import RadialMenuOverlay from "@/components/RadialMenuOverlay";
import WorkspaceSwitcherPopover from "@/components/orbital/WorkspaceSwitcherPopover";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";
import { useProject } from "@/context/ProjectContext";
import { QUICK_ACTIONS } from "@/lib/quickActions";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// Primary destinations that stay one click away in the persistent rail. The
// full constellation (company modules, daily brief, ideas, investments,
// plugins) remains one tap into the radial menu (Compass) below.
const RAIL_ITEMS: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/memory", label: "Memory", icon: BrainCircuit },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck },
  { to: "/automation", label: "Automation", icon: Zap },
  { to: "/integrations", label: "Integrations", icon: Plug },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

const railBtn = (active: boolean) =>
  clsx(
    "press-scale flex h-10 w-10 items-center justify-center rounded-xl border transition-all duration-200",
    active
      ? "border-jarvis-cyan/50 bg-jarvis-cyan/10 text-jarvis-cyan shadow-glow-sm"
      : "border-transparent text-jarvis-muted hover:border-jarvis-border hover:bg-jarvis-panel2/50 hover:text-jarvis-cyan"
  );

/**
 * The persistent left rail of the AI OS shell — always visible. Top: the
 * Jarvis AI Core (home) + the workspace/project switcher. Middle (scrolls):
 * primary navigation icons + the Quick Actions dock (each opens a studio
 * workspace inside the shell). Bottom: the Compass, which opens the full
 * radial menu of every route. Keeps the orbital aesthetic while making
 * navigation persistent.
 */
export default function RadialNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCompany } = useCompany();
  const { activeProjectId } = useProject();
  const { status } = useAssistantStatus();
  const [menuOpen, setMenuOpen] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const workspaceBtnRef = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState({ x: 0, y: 0 });

  function openSwitcher() {
    const rect = workspaceBtnRef.current?.getBoundingClientRect();
    if (rect) setAnchor({ x: rect.left + rect.width / 2, y: rect.bottom });
    setSwitcherOpen((v) => !v);
  }

  const projectsActive = location.pathname.startsWith("/projects") || location.pathname === "/company/projects";

  return (
    <>
      <aside className="hidden w-16 shrink-0 flex-col items-center gap-2 border-r border-jarvis-border/60 bg-jarvis-panel/50 py-3 backdrop-blur-2xl md:flex">
        {/* AI Core (home) */}
        <button
          onClick={() => navigate("/")}
          title="Home — Jarvis Core"
          className="press-scale shrink-0 rounded-full transition hover:shadow-glow-sm"
        >
          <JarvisCore state={status} size={40} />
        </button>

        {/* Workspace + project switcher */}
        <button
          ref={workspaceBtnRef}
          onClick={openSwitcher}
          title={activeCompany ? activeCompany.name : "No workspace"}
          className="press-scale flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-jarvis-border bg-jarvis-panel2/60 text-xs font-bold text-jarvis-cyan transition hover:border-jarvis-cyan/50"
        >
          {activeCompany ? initials(activeCompany.name) : "—"}
        </button>

        <div className="h-px w-8 shrink-0 bg-jarvis-border/60" />

        {/* Primary nav + Quick Actions dock (scrolls if the rail is short) */}
        <div className="flex min-h-0 flex-1 flex-col items-center gap-1.5 overflow-y-auto py-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <button
            onClick={() => navigate(activeProjectId ? `/projects/${activeProjectId}` : "/company/projects")}
            title="Projects"
            className={railBtn(projectsActive)}
          >
            <Rocket className="h-5 w-5" />
          </button>

          {RAIL_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} title={label} className={({ isActive }) => railBtn(isActive)}>
              <Icon className="h-5 w-5" />
            </NavLink>
          ))}

          <div className="my-1 h-px w-8 shrink-0 bg-jarvis-border/60" />

          {/* Quick Actions dock — each opens a studio workspace inside the shell */}
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.key}
              onClick={() => navigate(`/studio/${action.pluginName}`)}
              title={action.label}
              className={railBtn(location.pathname === `/studio/${action.pluginName}`)}
            >
              <action.icon className="h-[18px] w-[18px]" />
            </button>
          ))}
        </div>

        {/* Full radial menu */}
        <button
          onClick={() => setMenuOpen(true)}
          title="Navigate (radial menu)"
          className="press-scale flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan transition hover:bg-jarvis-cyan/20 hover:shadow-glow-sm"
        >
          <Compass className="h-5 w-5" />
        </button>
      </aside>

      <WorkspaceSwitcherPopover open={switcherOpen} onClose={() => setSwitcherOpen(false)} anchor={anchor} />
      <RadialMenuOverlay open={menuOpen} onClose={() => setMenuOpen(false)} />
    </>
  );
}
