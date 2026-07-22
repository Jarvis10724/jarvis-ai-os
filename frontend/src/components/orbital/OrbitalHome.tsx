import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  BrainCircuit,
  Building2,
  CalendarClock,
  FolderOpen,
  ListChecks,
  LineChart,
  Mail,
  Mic,
  Plug,
  ShieldCheck,
  Sunrise,
  Users,
  X,
} from "lucide-react";

import { api } from "@/api/client";
import ApprovalsCard from "@/components/ceo/ApprovalsCard";
import CalendarCard from "@/components/ceo/CalendarCard";
import GmailCard from "@/components/ceo/GmailCard";
import ConnectionLines from "@/components/orbital/ConnectionLines";
import MicDiagnosticPanel from "@/components/orbital/MicDiagnosticPanel";
import MobileCommandDeck from "@/components/orbital/MobileCommandDeck";
import OrbitalCore from "@/components/orbital/OrbitalCore";
import OrbitalNode from "@/components/orbital/OrbitalNode";
import OrbitRing from "@/components/orbital/OrbitRing";
import VoiceConsole from "@/components/orbital/VoiceConsole";
import WorkspaceSwitcherPopover from "@/components/orbital/WorkspaceSwitcherPopover";
import type { NodeSpec } from "@/components/orbital/types";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";
import { useDashboardUI } from "@/context/DashboardUIContext";
import { useMicrophoneDevices } from "@/hooks/useMicrophoneDevices";
import { useVoiceOrb, toCoreState } from "@/hooks/useVoiceOrb";
import { useWorkspace } from "@/hooks/useWorkspace";
import { MOCK_WATCHLIST } from "@/mock/investments";
import { showsInvestments } from "@/lib/companyModules";

function polar(cx: number, cy: number, radius: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
}

function timeAgo(iso: string | null): string {
  if (!iso) return "Not generated";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

type ExpandKey = "gmail" | "calendar" | "approvals" | null;

/**
 * The immersive AI-operating-system home view. Two concentric rings orbit
 * the AI Core:
 *   - System ring: Workspaces, Voice Command, Notifications — plus Stocks,
 *     which is context-aware and only appears for investment-oriented
 *     workspaces (see lib/companyModules.showsInvestments).
 *   - Workspace ring (company-scoped): Gmail, Calendar, Approval Center,
 *     Daily Brief, Files, Tasks, Contacts, AI Memory, Settings — every one
 *     of these reads/writes against whichever company is currently active.
 * The shell itself never branches per company — only the data underneath
 * the workspace ring does, driven entirely by CompanyContext's
 * activeCompanyId. Switching workspaces re-scopes every node in place.
 */
export default function OrbitalHome() {
  const navigate = useNavigate();
  const { activeCompany, activeCompanyId } = useCompany();
  const workspace = useWorkspace();
  const { setStatus } = useAssistantStatus();
  const { openNotifications } = useDashboardUI();

  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [expandedKey, setExpandedKey] = useState<ExpandKey>(null);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [diagOpen, setDiagOpen] = useState(false);

  // One microphone-devices instance shared by the Voice Console and the
  // diagnostics panel so selecting an input (e.g. an iPhone Continuity mic)
  // in one is reflected in the other and in the orb — no app restart.
  const mic = useMicrophoneDevices();

  // The AI Core is Jarvis's push-to-talk voice button — this engine drives
  // its animation states and also mirrors them to the global sidebar orb.
  const voice = useVoiceOrb({
    companyId: activeCompanyId,
    onStateChange: setStatus,
    deviceId: mic.selectedId,
  });
  const coreState = toCoreState(voice.state);

  // Hold Space to talk, release to stop — a push-to-talk shortcut scoped to
  // this screen (unmounts with it). Ignored while typing so Space still types.
  const voiceRef = useRef(voice);
  voiceRef.current = voice;
  useEffect(() => {
    function isTyping(t: EventTarget | null): boolean {
      if (!(t instanceof HTMLElement)) return false;
      return ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable;
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.code !== "Space" || e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTyping(e.target)) return;
      if (voiceRef.current.state !== "listening") {
        e.preventDefault();
        voiceRef.current.toggle();
      }
    }
    function onKeyUp(e: KeyboardEvent) {
      if (e.code !== "Space" || isTyping(e.target)) return;
      if (voiceRef.current.state === "listening") {
        e.preventDefault();
        voiceRef.current.stop();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  // Pointer parallax — writes normalized -1..1 offsets to CSS custom
  // properties on the container via rAF, so the depth layers shift without a
  // single React re-render (crucial with ~15 animated nodes on screen). The
  // layers read --par-x/--par-y at different multipliers for depth.
  const parallaxRaf = useRef<number | null>(null);
  function handleParallax(e: React.MouseEvent<HTMLDivElement>) {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const py = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    if (parallaxRaf.current) return;
    parallaxRaf.current = requestAnimationFrame(() => {
      el.style.setProperty("--par-x", px.toFixed(3));
      el.style.setProperty("--par-y", py.toFixed(3));
      parallaxRaf.current = null;
    });
  }
  function resetParallax() {
    const el = containerRef.current;
    if (!el) return;
    el.style.setProperty("--par-x", "0");
    el.style.setProperty("--par-y", "0");
  }

  const [stats, setStats] = useState<{
    gmailConnected: boolean | null;
    gmailUnread: number;
    approvalsPending: number;
    calendarConnected: boolean | null;
    calendarNext: string | null;
    briefingGeneratedAt: string | null;
    memoryCount: number | null;
  }>({
    gmailConnected: null,
    gmailUnread: 0,
    approvalsPending: 0,
    calendarConnected: null,
    calendarNext: null,
    briefingGeneratedAt: null,
    memoryCount: null,
  });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        const { width, height } = entry.contentRect;
        setSize({ width, height });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Re-fetch every workspace-scoped stat whenever the active company changes
  // — this is the "shell stays identical, only context changes" behavior.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const messages = await api.listGmailMessages({ companyId: activeCompanyId ?? undefined, unreadOnly: true, maxResults: 50 });
        if (!cancelled) setStats((s) => ({ ...s, gmailConnected: true, gmailUnread: messages.length }));
      } catch {
        if (!cancelled) setStats((s) => ({ ...s, gmailConnected: false, gmailUnread: 0 }));
      }
      try {
        const events = await api.listCalendarEvents({ companyId: activeCompanyId ?? undefined, maxResults: 5, upcomingOnly: true });
        if (!cancelled) setStats((s) => ({ ...s, calendarConnected: true, calendarNext: events[0]?.summary ?? null }));
      } catch {
        if (!cancelled) setStats((s) => ({ ...s, calendarConnected: false, calendarNext: null }));
      }
      try {
        const approvals = await api.listApprovals({ companyId: activeCompanyId ?? "any", status: "pending" });
        if (!cancelled) setStats((s) => ({ ...s, approvalsPending: approvals.length }));
      } catch {
        if (!cancelled) setStats((s) => ({ ...s, approvalsPending: 0 }));
      }
      try {
        const entries = await api.searchMemory({ companyId: activeCompanyId ?? "any", limit: 100 });
        if (!cancelled) setStats((s) => ({ ...s, memoryCount: entries.length }));
      } catch {
        if (!cancelled) setStats((s) => ({ ...s, memoryCount: null }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeCompanyId]);

  // Daily Brief isn't company-scoped on the backend today (one shared
  // briefing across all companies) — fetched once, not re-keyed on workspace.
  useEffect(() => {
    api
      .getLatestDailyBriefing()
      .then((b) => setStats((s) => ({ ...s, briefingGeneratedAt: b?.generated_at ?? null })))
      .catch(() => {
        // no briefing yet — leave null
      });
  }, []);

  const { width, height } = size;
  // Phone (portrait or short-landscape) → the thumb-first command deck; wider
  // viewports → the full orbital constellation. The full circle clips on a
  // phone, so we don't even try it there.
  const compact = width > 0 && (width < 700 || height < 560);
  // Mobile Core hero diameter — fits the ~42vh hero (clamped 224–380 in the
  // deck) and the viewport width, so the Core never overflows into the dock.
  const heroHeight = Math.min(380, Math.max(224, height * 0.42));
  const mobileCoreDiameter = Math.max(180, Math.min(width - 56, heroHeight - 8, 340));

  // Reserve room at the bottom for the fixed VoiceConsole so the lowest
  // orbital node never sits behind it — the whole constellation shifts up.
  const BOTTOM_RESERVE = 104;
  const cx = width / 2;
  const cy = Math.max(height / 2 - BOTTOM_RESERVE / 2, height * 0.42);
  const shortSide = Math.min(width, height) || 0;
  const narrow = width < 480; // phone portrait
  // Keep the whole constellation inside the viewport so no orbital node clips
  // off the right/left edge on a phone. `maxRadius` is the furthest a node
  // center can sit and still leave room for its ~40px half-width + margin.
  const maxRadius = Math.max(120, width / 2 - 72);
  const coreDiameter = Math.min(Math.max(shortSide * 0.46, narrow ? 168 : 260), 620);
  const innerRadius = Math.min(Math.max(110, shortSide * 0.24), maxRadius * 0.7);
  const outerRadius = Math.min(Math.max(190, shortSide * 0.42), maxRadius);

  const systemSpecs: NodeSpec[] = useMemo(
    () => [
      {
        key: "workspaces",
        icon: Building2,
        label: "Workspaces",
        sublabel: activeCompany ? activeCompany.name : "None active",
        tone: "cyan",
        active: switcherOpen,
        onClick: () => setSwitcherOpen((v) => !v),
      },
      {
        key: "voice",
        icon: Mic,
        label: "Voice Command",
        sublabel: "Talk to Jarvis",
        tone: "violet",
        onClick: () => navigate("/chat?voice=1"),
      },
      {
        key: "notifications",
        icon: Bell,
        label: "Notifications",
        sublabel: "System alerts",
        tone: "amber",
        onClick: () => openNotifications(),
      },
      // Stocks / market module — only for investment-oriented workspaces
      // (e.g. Greener Capitol), hidden for SPN Group LLC.
      ...(showsInvestments(activeCompany)
        ? [
            {
              key: "stocks",
              icon: LineChart,
              label: "Stocks",
              sublabel: `${MOCK_WATCHLIST[0]?.symbol ?? "Markets"} ${
                MOCK_WATCHLIST[0]
                  ? (MOCK_WATCHLIST[0].change >= 0 ? "+" : "") + MOCK_WATCHLIST[0].changePercent.toFixed(1) + "%"
                  : ""
              }`,
              tone: "blue" as const,
              onClick: () => navigate("/investments"),
            },
          ]
        : []),
    ],
    [activeCompany, switcherOpen, openNotifications, navigate]
  );

  const workspaceSpecs: NodeSpec[] = useMemo(
    () => [
      {
        key: "gmail",
        icon: Mail,
        label: "Gmail",
        sublabel: stats.gmailConnected === false ? "Not connected" : `${stats.gmailUnread} unread`,
        tone: "blue",
        badge: stats.gmailConnected ? stats.gmailUnread || undefined : undefined,
        active: expandedKey === "gmail",
        onClick: () => setExpandedKey((k) => (k === "gmail" ? null : "gmail")),
      },
      {
        key: "calendar",
        icon: CalendarClock,
        label: "Calendar",
        sublabel: stats.calendarConnected === false ? "Not connected" : stats.calendarNext ?? "No upcoming events",
        tone: "cyan",
        active: expandedKey === "calendar",
        onClick: () => setExpandedKey((k) => (k === "calendar" ? null : "calendar")),
      },
      {
        key: "approvals",
        icon: ShieldCheck,
        label: "Approval Center",
        sublabel: stats.approvalsPending > 0 ? `${stats.approvalsPending} pending` : "All clear",
        tone: "amber",
        badge: stats.approvalsPending || undefined,
        active: expandedKey === "approvals",
        onClick: () => setExpandedKey((k) => (k === "approvals" ? null : "approvals")),
      },
      {
        key: "daily-brief",
        icon: Sunrise,
        label: "Daily Brief",
        sublabel: timeAgo(stats.briefingGeneratedAt),
        tone: "cyan",
        onClick: () => navigate("/daily-brief"),
      },
      {
        key: "files",
        icon: FolderOpen,
        label: "Files",
        sublabel: "Documents",
        tone: "violet",
        onClick: () => navigate("/company?tab=documents"),
      },
      {
        key: "tasks",
        icon: ListChecks,
        label: "Tasks",
        sublabel: "Project Manager",
        tone: "emerald",
        onClick: () => navigate("/company/projects"),
      },
      {
        key: "contacts",
        icon: Users,
        label: "Contacts",
        sublabel: "CRM",
        tone: "blue",
        onClick: () => navigate("/company/crm"),
      },
      {
        key: "memory",
        icon: BrainCircuit,
        label: "AI Memory",
        sublabel:
          stats.memoryCount === null
            ? "Workspace recall"
            : `${stats.memoryCount}${stats.memoryCount === 100 ? "+" : ""} ${stats.memoryCount === 1 ? "memory" : "memories"}`,
        tone: "violet",
        onClick: () => navigate(activeCompanyId ? `/memory?company=${activeCompanyId}` : "/memory"),
      },
      {
        key: "settings",
        icon: Plug,
        label: "Settings",
        sublabel: "Integrations",
        tone: "rose",
        onClick: () => navigate(activeCompanyId ? `/integrations?company=${activeCompanyId}` : "/integrations"),
      },
    ],
    [stats, expandedKey, activeCompanyId, navigate]
  );

  const systemPositions = systemSpecs.map((spec, i) => ({
    spec,
    ...polar(cx, cy, innerRadius, -90 + (360 / systemSpecs.length) * i),
  }));
  const workspacePositions = workspaceSpecs.map((spec, i) => ({
    spec,
    ...polar(cx, cy, outerRadius, -90 + (360 / workspaceSpecs.length) * i + 14),
  }));

  const workspacesNodePos = systemPositions.find((p) => p.spec.key === "workspaces");

  const ready = width > 0 && height > 0;

  const processing = coreState !== "idle";
  const coreHint = voice.state === "listening"
    ? "Listening — release Space to send"
    : voice.available
      ? "Tap the core or hold Space to talk"
      : voice.detail
        ? "Voice unavailable — type below"
        : undefined;

  // Core identity — the workspace's name + its *kind* ("Innovation Hub",
  // "Consumer Brands"), so switching companies visibly changes the Core's
  // identity, not just its accent.
  const coreTitle = activeCompany ? activeCompany.name.toUpperCase() : "JARVIS";
  const coreSubtitle = (activeCompany ? workspace.role : "AI Operating System").toUpperCase();

  // The switcher popover anchors under the Workspaces node on desktop; on
  // mobile there's no such node, so it drops from just below the top bar.
  const switcherAnchor = compact
    ? { x: width / 2, y: 12 }
    : workspacesNodePos
      ? { x: workspacesNodePos.x, y: workspacesNodePos.y + 40 }
      : { x: width / 2, y: 120 };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleParallax}
      onMouseLeave={resetParallax}
      className="relative h-full w-full overflow-hidden"
    >
      {/* Deep background layer — drifts further with the pointer for depth. */}
      <div
        className="parallax-layer absolute inset-0"
        style={{ transform: "translate3d(calc(var(--par-x, 0) * 20px), calc(var(--par-y, 0) * 20px), 0)" }}
        aria-hidden="true"
      >
        <div className="starfield" />
        {ready && !compact && (
          <>
            <OrbitRing diameter={outerRadius * 2 + 140} durationSec={90} opacity={0.08} />
            <OrbitRing diameter={innerRadius * 2 + 90} durationSec={70} reverse opacity={0.1} />
          </>
        )}
      </div>

      {/* Mobile: thumb-first command deck. */}
      {ready && compact && (
        <MobileCommandDeck
          coreDiameter={mobileCoreDiameter}
          coreState={coreState}
          coreTitle={coreTitle}
          coreSubtitle={coreSubtitle}
          hint={coreHint}
          level={voice.level}
          onCoreClick={voice.toggle}
          dockSpecs={systemSpecs}
          gridSpecs={workspaceSpecs}
        />
      )}

      {/* Desktop: full orbital constellation. */}
      {ready && !compact && (
        <div
          className="parallax-layer absolute inset-0"
          style={{ transform: "translate3d(calc(var(--par-x, 0) * -7px), calc(var(--par-y, 0) * -7px), 0)" }}
        >
          <ConnectionLines
            width={width}
            height={height}
            origin={{ x: cx, y: cy }}
            points={[...systemPositions, ...workspacePositions].map((p) => ({ x: p.x, y: p.y }))}
            active={processing}
          />

          <OrbitalCore
            diameter={coreDiameter}
            state={coreState}
            title={coreTitle}
            subtitle={coreSubtitle}
            hint={coreHint}
            level={voice.level}
            onClick={voice.toggle}
          />

          {systemPositions.map(({ spec, x, y }, i) => (
            <OrbitalNode
              key={spec.key}
              x={x}
              y={y}
              icon={spec.icon}
              label={spec.label}
              sublabel={spec.sublabel}
              tone={spec.tone}
              badge={spec.badge}
              active={spec.active}
              delay={i * 0.06}
              compact
              onClick={spec.onClick}
            />
          ))}

          {workspacePositions.map(({ spec, x, y }, i) => (
            <OrbitalNode
              key={spec.key}
              x={x}
              y={y}
              icon={spec.icon}
              label={spec.label}
              sublabel={spec.sublabel}
              tone={spec.tone}
              badge={spec.badge}
              active={spec.active}
              delay={0.24 + i * 0.05}
              onClick={spec.onClick}
            />
          ))}

        </div>
      )}

      {/* Shared across both layouts — anchored per layout above. */}
      {ready && (
        <WorkspaceSwitcherPopover
          open={switcherOpen}
          onClose={() => setSwitcherOpen(false)}
          anchor={switcherAnchor}
        />
      )}

      <AnimatePresence>
        {expandedKey && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setExpandedKey(null)}
              className="fixed inset-0 z-40 bg-black/70 backdrop-blur-md"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 12 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2"
              style={{ width: 420, maxWidth: "92vw" }}
            >
              <div className="relative">
                <button
                  onClick={() => setExpandedKey(null)}
                  className="press-scale absolute -right-2 -top-2 z-10 rounded-full border border-jarvis-border bg-jarvis-panel p-1.5 text-jarvis-muted shadow-elevated transition hover:text-jarvis-text"
                >
                  <X className="h-4 w-4" />
                </button>
                <div className="overflow-hidden rounded-2xl shadow-elevated-lg" style={{ height: 440, maxHeight: "70vh" }}>
                  {expandedKey === "gmail" && <GmailCard companyId={activeCompanyId ?? undefined} />}
                  {expandedKey === "calendar" && <CalendarCard companyId={activeCompanyId ?? undefined} />}
                  {expandedKey === "approvals" && <ApprovalsCard companyId={activeCompanyId ?? undefined} />}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <VoiceConsole voice={voice} mic={mic} onOpenDiagnostics={() => setDiagOpen(true)} />
      <MicDiagnosticPanel open={diagOpen} onClose={() => setDiagOpen(false)} voice={voice} mic={mic} />
    </div>
  );
}
