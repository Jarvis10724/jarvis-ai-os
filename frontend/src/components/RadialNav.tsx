import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Compass } from "lucide-react";

import JarvisCore from "@/components/JarvisCore";
import RadialMenuOverlay from "@/components/RadialMenuOverlay";
import WorkspaceSwitcherPopover from "@/components/orbital/WorkspaceSwitcherPopover";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

/**
 * The persistent left rail — deliberately minimal. Traditional sidebars list
 * every route at once; this app's navigation instead lives in
 * RadialMenuOverlay (a full-screen radial menu), reachable from the compass
 * button below. The rail only surfaces the two things worth being
 * always-visible: the Jarvis brand mark (home) and which workspace is
 * active — everything else is one tap into the radial menu away.
 */
export default function RadialNav() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
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

  return (
    <>
      <aside className="hidden w-20 shrink-0 flex-col items-center gap-3 border-r border-jarvis-border/60 bg-jarvis-panel/50 py-4 backdrop-blur-2xl md:flex">
        <button
          onClick={() => navigate("/")}
          title="Home"
          className="press-scale rounded-full transition hover:shadow-glow-sm"
        >
          <JarvisCore state={status} size={40} />
        </button>

        <button
          ref={workspaceBtnRef}
          onClick={openSwitcher}
          title={activeCompany ? activeCompany.name : "No workspace"}
          className="press-scale flex h-10 w-10 items-center justify-center rounded-full border border-jarvis-border bg-jarvis-panel2/60 text-xs font-bold text-jarvis-cyan transition hover:border-jarvis-cyan/50"
        >
          {activeCompany ? initials(activeCompany.name) : "—"}
        </button>

        <div className="flex-1" />

        <button
          onClick={() => setMenuOpen(true)}
          title="Navigate (radial menu)"
          className="press-scale flex h-11 w-11 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan transition hover:bg-jarvis-cyan/20 hover:shadow-glow-sm"
        >
          <Compass className="h-5 w-5" />
        </button>
      </aside>

      <WorkspaceSwitcherPopover open={switcherOpen} onClose={() => setSwitcherOpen(false)} anchor={anchor} />
      <RadialMenuOverlay open={menuOpen} onClose={() => setMenuOpen(false)} />
    </>
  );
}
