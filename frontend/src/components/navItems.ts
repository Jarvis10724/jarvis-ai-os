import {
  Blocks,
  Home,
  MessageSquare,
  Plug,
  Rocket,
  Settings as SettingsIcon,
  ShieldCheck,
  Zap,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "CEO Dashboard", icon: Home, end: true },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/projects", label: "Projects", icon: Rocket },
  { to: "/plugins", label: "Plugins", icon: Blocks },
  { to: "/automation", label: "Automation", icon: Zap },
  { to: "/integrations", label: "Integrations", icon: Plug },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];
