import {
  Blocks,
  Boxes,
  BookOpen,
  BrainCircuit,
  CalendarDays,
  DollarSign,
  Factory,
  Globe,
  Home,
  LayoutDashboard,
  Lightbulb,
  LineChart,
  Megaphone,
  MessageSquare,
  PackageSearch,
  Plug,
  Rocket,
  Settings as SettingsIcon,
  Sunrise,
  Users,
  Zap,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import clsx from "clsx";

import CompanySwitcher from "@/components/CompanySwitcher";
import JarvisCore from "@/components/JarvisCore";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";

// Exported so CommandPalette can flatten these into "jump to any page"
// entries without a second, separately-maintained route registry.
export const GLOBAL_ITEMS = [
  { to: "/", label: "Overview", icon: Home, end: true },
  { to: "/daily-brief", label: "Daily Brief", icon: Sunrise },
  { to: "/investments", label: "Investment Dashboard", icon: LineChart },
  { to: "/ideas", label: "Idea Incubator", icon: Lightbulb },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/memory", label: "Memory", icon: BrainCircuit },
];

export const WORKSPACE_ITEMS = [
  { to: "/company/dashboard", label: "Company Dashboard", icon: LayoutDashboard },
  { to: "/company/projects", label: "Project Manager", icon: Rocket },
  { to: "/company/crm", label: "CRM", icon: Users },
  { to: "/company/sops", label: "SOP Library", icon: BookOpen },
  { to: "/company/manufacturing-tracker", label: "Manufacturing Tracker", icon: Factory },
  { to: "/company/inventory", label: "Inventory", icon: Boxes },
  { to: "/company/financials", label: "Financial Dashboard", icon: DollarSign },
  { to: "/company/marketing-studio", label: "AI Marketing Studio", icon: Megaphone },
  { to: "/company/content-calendar", label: "Content Calendar", icon: CalendarDays },
  { to: "/company/website-builder", label: "Website Builder", icon: Globe },
  { to: "/company/amazon-launch", label: "Amazon Launch Center", icon: PackageSearch },
];

export const SYSTEM_ITEMS = [
  { to: "/plugins", label: "Plugins", icon: Blocks },
  { to: "/automation", label: "Automation", icon: Zap },
  { to: "/integrations", label: "Integrations", icon: Plug },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export type NavEntry = { to: string; label: string; icon: typeof Home; end?: boolean };

function NavSection({
  label,
  items,
  delayOffset = 0,
  onNavigate,
}: {
  label?: string;
  items: NavEntry[];
  delayOffset?: number;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      {label && (
        <p className="px-3.5 pb-1.5 pt-4 text-[10px] font-semibold uppercase tracking-widest text-jarvis-faint">
          {label}
        </p>
      )}
      {items.map(({ to, label: itemLabel, icon: Icon, end }, i) => (
        <motion.div
          key={to}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.03 * (delayOffset + i), duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <NavLink
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "group relative flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                  : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={clsx(
                    "absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-jarvis-cyan transition-opacity duration-200",
                    isActive ? "opacity-100" : "opacity-0"
                  )}
                />
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{itemLabel}</span>
              </>
            )}
          </NavLink>
        </motion.div>
      ))}
    </div>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { activeCompany } = useCompany();

  return (
    <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 pb-4">
      <NavSection items={GLOBAL_ITEMS} onNavigate={onNavigate} />
      {activeCompany && (
        <NavSection
          label={`Workspace — ${activeCompany.name}`}
          items={WORKSPACE_ITEMS}
          delayOffset={GLOBAL_ITEMS.length}
          onNavigate={onNavigate}
        />
      )}
      <NavSection
        label="System"
        items={SYSTEM_ITEMS}
        delayOffset={GLOBAL_ITEMS.length + WORKSPACE_ITEMS.length}
        onNavigate={onNavigate}
      />
    </nav>
  );
}

export function SidebarBrand() {
  // Global "is Jarvis working" indicator — reflects real assistant state
  // (listening/thinking/speaking) from ChatPanel no matter which page is
  // currently open, not just while Chat itself is on screen.
  const { status } = useAssistantStatus();
  return (
    <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-jarvis-border/60 px-6">
      <JarvisCore state={status} size={22} />
      <span className="font-display text-lg font-bold tracking-[0.2em] text-jarvis-text text-glow">
        JARVIS
      </span>
    </div>
  );
}

export function SystemLoadCard() {
  return (
    <div className="m-3 shrink-0 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-4">
      <div className="mb-2 flex items-center justify-between text-xs text-jarvis-muted">
        <span>System Load</span>
        <span className="font-data text-jarvis-cyan">Nominal</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-jarvis-border/50">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-jarvis-cyan to-jarvis-blue"
          initial={{ width: 0 }}
          animate={{ width: "66%" }}
          transition={{ duration: 1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  );
}

export default function Sidebar() {
  return (
    <aside className="hidden w-72 shrink-0 flex-col border-r border-jarvis-border/60 bg-jarvis-panel/50 backdrop-blur-2xl md:flex">
      <SidebarBrand />
      <CompanySwitcher />
      <SidebarNav />
      <SystemLoadCard />
    </aside>
  );
}
